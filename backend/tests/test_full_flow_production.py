"""
PetCircle — Full End-to-End Test Flow (Production Credentials)

Uses TEST_PHONE_NUMBER from .env.production to run the complete pipeline:
  1. Clean up any existing test data for the phone number
  2. Full onboarding (consent → name → pincode → pet profile → food/grooming)
  3. Upload all supported docs from 'pet condition docs' folder to Supabase
  4. Run GPT extraction on every uploaded document
  5. Report all results

Run from backend/ directory:
    APP_ENV=production python -m tests.test_full_flow_production

Zayn's profile (used throughout):
  - Owner: Rahul Sharma, Pincode 400001
  - Pet: Zayn, Male dog, Labrador Retriever, DOB 15/06/2019, Weight 28kg, Neutered
  - Food: Royal Canin (packaged)
"""

import asyncio
import logging
import os
import sys

# Fix Windows console encoding for UTF-8 output
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure APP_ENV=production so production credentials are loaded.
os.environ.setdefault("APP_ENV", "production")

# Add project root to path so app imports work when running as a module.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_full_flow")

from app.config import settings
from app.core.encryption import decrypt_field, hash_field
from app.database import SessionLocal
from app.models.condition import Condition
from app.models.condition_medication import ConditionMedication
from app.models.condition_monitoring import ConditionMonitoring
from app.models.conflict_flag import ConflictFlag
from app.models.contact import Contact
from app.models.dashboard_token import DashboardToken
from app.models.diagnostic_test_result import DiagnosticTestResult
from app.models.document import Document
from app.models.pet import Pet
from app.models.preventive_record import PreventiveRecord
from app.models.reminder import Reminder
from app.models.user import User
from app.services.document_upload import (
    build_storage_path,
    create_document_record,
    upload_to_supabase,
    validate_file_upload,
)
from app.services.gpt_extraction import extract_and_process_document
from app.services.onboarding import create_pending_user, handle_onboarding_step

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" -- {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print("=" * 65)


# Mock WhatsApp sender — captures what would be sent without hitting the API.
_sent_messages: list[dict] = []


async def mock_send(db, to: str, text: str) -> None:
    _sent_messages.append({"to": to, "text": text[:120]})
    print(f"    [WA->{to}] {text[:120]}")


# ---------------------------------------------------------------------------
# Document files to upload (only PDF / JPG from 'pet condition docs')
# ---------------------------------------------------------------------------

DOCS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "pet condition docs"
)

# Supported MIME types by extension
_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
}

# Priority list — upload these first (most medically relevant)
_PRIORITY_FILES = [
    "Zayn_Vaccination_Record_1(1).jpg",
    "Zayn_Vaccination_Record_2(1).jpg",
    "ZAYN_BLOOD_REPORT_sep25(1).pdf",
    "Zayn_UrineCulture_sep25(1).pdf",
    "zayn_urine_Oct25(1).pdf",
    "zayn_urine_sep25(1).pdf",
    "zayn_usg_film_Sep25(1).pdf",
    "Zayn_x-ray_report_sep25(1).pdf",
    "Prescription_Chavan_12_02_25.jpg",
    "Zayn_usg_report_sep25.pdf",
]


def _get_upload_files(max_files: int = 10) -> list[dict]:
    """
    Return up to max_files uploadable files from the pet condition docs folder.
    Priority list first, then remaining supported files, skipping .docx etc.
    """
    docs_dir = os.path.abspath(DOCS_DIR)
    if not os.path.isdir(docs_dir):
        logger.error("pet condition docs directory not found: %s", docs_dir)
        return []

    all_files = set(os.listdir(docs_dir))
    chosen: list[dict] = []

    # First pass: priority files that actually exist
    for fname in _PRIORITY_FILES:
        if len(chosen) >= max_files:
            break
        if fname not in all_files:
            continue
        ext = os.path.splitext(fname)[1].lower()
        mime = _MIME_MAP.get(ext)
        if not mime:
            continue
        fpath = os.path.join(docs_dir, fname)
        size = os.path.getsize(fpath)
        if size > 10 * 1024 * 1024:
            logger.warning("Skipping %s — exceeds 10MB (%d bytes)", fname, size)
            continue
        chosen.append({"name": fname, "path": fpath, "mime": mime, "size": size})

    # Second pass: any remaining supported files not already chosen
    chosen_names = {f["name"] for f in chosen}
    for fname in sorted(all_files):
        if len(chosen) >= max_files:
            break
        if fname in chosen_names:
            continue
        ext = os.path.splitext(fname)[1].lower()
        mime = _MIME_MAP.get(ext)
        if not mime:
            continue
        fpath = os.path.join(docs_dir, fname)
        size = os.path.getsize(fpath)
        if size > 10 * 1024 * 1024:
            logger.warning("Skipping %s — exceeds 10MB (%d bytes)", fname, size)
            continue
        chosen.append({"name": fname, "path": fpath, "mime": mime, "size": size})

    return chosen


# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------


def _cleanup_test_user(db, mobile: str) -> None:
    """Remove all data for the test mobile number."""
    mobile_h = hash_field(mobile)
    user = db.query(User).filter(User.mobile_hash == mobile_h).first()
    if not user:
        print("  No existing data to clean up.")
        return

    pets = db.query(Pet).filter(Pet.user_id == user.id).all()
    for pet in pets:
        db.query(DashboardToken).filter(DashboardToken.pet_id == pet.id).delete()
        db.query(DiagnosticTestResult).filter(DiagnosticTestResult.pet_id == pet.id).delete()
        db.query(Condition).filter(Condition.pet_id == pet.id).delete()
        db.query(Contact).filter(Contact.pet_id == pet.id).delete()
        db.query(Document).filter(Document.pet_id == pet.id).delete()
        records = db.query(PreventiveRecord).filter(PreventiveRecord.pet_id == pet.id).all()
        for rec in records:
            db.query(Reminder).filter(Reminder.preventive_record_id == rec.id).delete()
            db.query(ConflictFlag).filter(ConflictFlag.preventive_record_id == rec.id).delete()
        db.query(PreventiveRecord).filter(PreventiveRecord.pet_id == pet.id).delete()
    db.query(Pet).filter(Pet.user_id == user.id).delete()
    db.query(User).filter(User.id == user.id).delete()
    db.commit()
    print(f"  Cleaned up existing test data for mobile {mobile[:6]}****")


# ---------------------------------------------------------------------------
# Main test flow
# ---------------------------------------------------------------------------


async def run() -> int:
    global PASS, FAIL

    # Resolve TEST_PHONE_NUMBER from env (strip leading '+')
    raw_phone = os.environ.get("TEST_PHONE_NUMBER") or getattr(settings, "TEST_PHONE_NUMBER", None)
    if not raw_phone:
        # Fall back: reload from env file directly
        from pathlib import Path
        env_path = Path(__file__).resolve().parent.parent / "envs" / ".env.production"
        for line in env_path.read_text().splitlines():
            if line.startswith("TEST_PHONE_NUMBER="):
                raw_phone = line.split("=", 1)[1].strip()
                break

    if not raw_phone:
        print("ERROR: TEST_PHONE_NUMBER not found in .env.production")
        return 1

    test_mobile = raw_phone.lstrip("+")  # e.g. "15551657226"
    print(f"\n{'#' * 65}")
    print(f"  PetCircle Full Flow Test — Phone: +{test_mobile}")
    print(f"  ENV: {os.environ.get('APP_ENV', 'production')}")
    print(f"  DB:  {settings.DATABASE_URL[:40]}...")
    print(f"{'#' * 65}")

    db = SessionLocal()

    try:
        # ===========================================================
        section("STEP 0 — CLEANUP")
        # ===========================================================
        _cleanup_test_user(db, test_mobile)

        # ===========================================================
        section("STEP 1 — ONBOARDING: CONSENT & OWNER DETAILS")
        # ===========================================================

        user = create_pending_user(db, test_mobile)
        check("User created (awaiting_consent)", user is not None)
        check("Initial state = awaiting_consent", user.onboarding_state == "awaiting_consent")

        user._plaintext_mobile = test_mobile

        # 1. Consent
        await handle_onboarding_step(db, user, "yes", mock_send)
        db.refresh(user)
        check("Consent accepted", user.consent_given == True)
        check("State → awaiting_name", user.onboarding_state == "awaiting_name")

        # 2. Owner name
        await handle_onboarding_step(db, user, "Rahul Sharma", mock_send)
        db.refresh(user)
        check("Name stored", user.full_name == "Rahul Sharma")
        check("State → awaiting_pincode", user.onboarding_state == "awaiting_pincode")

        # 3. Pincode
        await handle_onboarding_step(db, user, "400001", mock_send)
        db.refresh(user)
        check("Pincode stored (encrypted)", decrypt_field(user.pincode) == "400001")
        check("State → awaiting_pet_name", user.onboarding_state == "awaiting_pet_name")

        # ===========================================================
        section("STEP 2 — ONBOARDING: PET PROFILE")
        # ===========================================================

        # 4. Pet name
        await handle_onboarding_step(db, user, "Zayn", mock_send)
        db.refresh(user)
        pet = db.query(Pet).filter(Pet.user_id == user.id).first()
        check("Pet created with name 'Zayn'", pet is not None and pet.name == "Zayn")
        print(f"    State after pet name: {user.onboarding_state}")

        # 5. Pet photo — skip
        if user.onboarding_state == "awaiting_pet_photo":
            await handle_onboarding_step(db, user, "skip", mock_send)
            db.refresh(user)
            print(f"    State after photo skip: {user.onboarding_state}")

        # 6. Species
        if user.onboarding_state == "awaiting_species":
            await handle_onboarding_step(db, user, "dog", mock_send)
            db.refresh(user)
            if pet:
                db.refresh(pet)
            print(f"    State after species: {user.onboarding_state}")

        # Handle species confirm if triggered
        if user.onboarding_state == "awaiting_species_confirm":
            await handle_onboarding_step(db, user, "yes", mock_send)
            db.refresh(user)
            if pet:
                db.refresh(pet)
            print(f"    State after species confirm: {user.onboarding_state}")

        # Handle breed confirm if photo AI detected breed
        if user.onboarding_state == "awaiting_breed_confirm":
            await handle_onboarding_step(db, user, "Labrador Retriever", mock_send)
            db.refresh(user)
            if pet:
                db.refresh(pet)
            print(f"    State after breed confirm: {user.onboarding_state}")

        # 7. Breed (if not yet set from photo AI)
        if user.onboarding_state == "awaiting_breed":
            await handle_onboarding_step(db, user, "Labrador Retriever", mock_send)
            db.refresh(user)
            if pet:
                db.refresh(pet)
            print(f"    State after breed: {user.onboarding_state}")

        if pet:
            db.refresh(pet)
        check("Species = dog", pet is not None and pet.species == "dog")
        check("Breed stored", pet is not None and pet.breed is not None)
        print(f"    Breed: {pet.breed if pet else 'N/A'}")
        check("State → awaiting_gender", user.onboarding_state == "awaiting_gender")

        # 8. Gender
        await handle_onboarding_step(db, user, "male", mock_send)
        db.refresh(user)
        db.refresh(pet)
        check("Gender = male", pet.gender == "male")
        check("State → awaiting_dob", user.onboarding_state == "awaiting_dob")

        # 9. DOB
        await handle_onboarding_step(db, user, "15/06/2019", mock_send)
        db.refresh(user)
        db.refresh(pet)
        print(f"    State after DOB: {user.onboarding_state}")

        # Handle DOB ambiguity confirmation if needed
        if user.onboarding_state == "awaiting_dob_confirm":
            await handle_onboarding_step(db, user, "yes", mock_send)
            db.refresh(user)
            db.refresh(pet)
            print(f"    State after DOB confirm: {user.onboarding_state}")

        check("DOB stored", pet.dob is not None)
        print(f"    DOB: {pet.dob}")
        check("State → awaiting_weight", user.onboarding_state == "awaiting_weight")

        # 10. Weight
        await handle_onboarding_step(db, user, "28", mock_send)
        db.refresh(user)
        db.refresh(pet)
        print(f"    State after weight: {user.onboarding_state}")

        # Handle weight confirmation if needed
        if user.onboarding_state == "awaiting_weight_confirm":
            await handle_onboarding_step(db, user, "yes", mock_send)
            db.refresh(user)
            db.refresh(pet)
            print(f"    State after weight confirm: {user.onboarding_state}")

        check("Weight stored", pet.weight is not None)
        print(f"    Weight: {pet.weight} kg")
        check("State → awaiting_neutered", user.onboarding_state == "awaiting_neutered")

        # 11. Neutered
        await handle_onboarding_step(db, user, "yes", mock_send)
        db.refresh(user)
        db.refresh(pet)
        check("Neutered = True", pet.neutered == True)
        print(f"    State after neutered: {user.onboarding_state}")

        # ===========================================================
        section("STEP 3 — ONBOARDING: FOOD, SUPPLEMENTS & GROOMING")
        # ===========================================================

        # 12. Packaged food
        if user.onboarding_state == "awaiting_packaged_food":
            await handle_onboarding_step(db, user, "Royal Canin Medium Adult", mock_send)
            db.refresh(user)
            check("State advanced from packaged_food", user.onboarding_state != "awaiting_packaged_food")
            print(f"    State after packaged food: {user.onboarding_state}")

        # 13. Homemade food
        if user.onboarding_state == "awaiting_homemade_food":
            await handle_onboarding_step(db, user, "skip", mock_send)
            db.refresh(user)
            print(f"    State after homemade food: {user.onboarding_state}")

        # 14. Supplements
        if user.onboarding_state == "awaiting_supplements":
            await handle_onboarding_step(db, user, "skip", mock_send)
            db.refresh(user)
            print(f"    State after supplements: {user.onboarding_state}")

        # 15. Grooming
        if user.onboarding_state == "awaiting_grooming":
            await handle_onboarding_step(db, user, "skip", mock_send)
            db.refresh(user)
            print(f"    State after grooming: {user.onboarding_state}")

        # 16. Document upload window — skip to complete onboarding
        if user.onboarding_state == "awaiting_documents":
            await handle_onboarding_step(db, user, "skip", mock_send)
            db.refresh(user)
            print(f"    State after doc window skip: {user.onboarding_state}")

        check("Onboarding complete", user.onboarding_state == "complete")

        # Verify preventive records seeded
        db.refresh(pet)
        records = db.query(PreventiveRecord).filter(PreventiveRecord.pet_id == pet.id).all()
        check("Preventive records seeded", len(records) > 0, f"got {len(records)}")
        print(f"    Preventive records: {len(records)}")
        for r in records:
            iname = (r.preventive_master.item_name if r.preventive_master else
                     r.custom_preventive_item.item_name if r.custom_preventive_item else "?")
            print(f"      - {iname}: status={r.status}, last={r.last_done_date}, next={r.next_due_date}")

        # Verify dashboard token
        token_rec = db.query(DashboardToken).filter(DashboardToken.pet_id == pet.id).first()
        check("Dashboard token generated", token_rec is not None)
        if token_rec:
            print(f"    Dashboard token: {token_rec.token}")
            print(f"    Dashboard URL (local): http://localhost:3000/dashboard/{token_rec.token}")

        # ===========================================================
        section("STEP 4 — DOCUMENT UPLOAD TO SUPABASE")
        # ===========================================================

        upload_files = _get_upload_files(max_files=10)
        check("Pet condition docs found", len(upload_files) > 0, f"found {len(upload_files)}")
        print(f"\n  Files to upload ({len(upload_files)}):")
        for f in upload_files:
            print(f"    • {f['name']} ({f['mime']}, {f['size'] // 1024} KB)")

        uploaded_doc_ids: list = []

        for i, file_info in enumerate(upload_files, start=1):
            fname = file_info["name"]
            fpath = file_info["path"]
            mime = file_info["mime"]
            fsize = file_info["size"]

            print(f"\n  [{i}/{len(upload_files)}] {fname}")

            # Read file bytes
            with open(fpath, "rb") as fh:
                file_bytes = fh.read()

            try:
                validate_file_upload(fsize, mime)
            except ValueError as e:
                check(f"Validate {fname}", False, str(e))
                continue

            check(f"  Validate {fname}", True)

            # Build storage path and upload
            file_path = build_storage_path(str(user.id), str(pet.id), fname)
            try:
                result_path = await upload_to_supabase(file_bytes, file_path, mime)
                check("  Upload to Supabase", True)
                print(f"    Path: {result_path}")
            except Exception as e:
                check(f"  Upload to Supabase ({fname})", False, str(e))
                continue

            # Create document DB record
            try:
                doc = create_document_record(db, pet.id, file_path, mime)
                check("  Document record created (status=pending)", doc.extraction_status == "pending")
                uploaded_doc_ids.append(doc.id)
            except Exception as e:
                check(f"  Document record ({fname})", False, str(e))
                continue

            # Small delay to avoid rate limits
            await asyncio.sleep(0.5)

        print(f"\n  Total uploaded: {len(uploaded_doc_ids)} / {len(upload_files)}")

        # ===========================================================
        section("STEP 5 — GPT EXTRACTION ON UPLOADED DOCUMENTS")
        # ===========================================================

        if not uploaded_doc_ids:
            print("  No documents uploaded — skipping extraction.")
        else:
            extraction_results: list[dict] = []

            for i, doc_id in enumerate(uploaded_doc_ids, start=1):
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if not doc:
                    continue
                fname = os.path.basename(doc.file_path)
                print(f"\n  [{i}/{len(uploaded_doc_ids)}] Extracting: {fname}")

                # Read file bytes again for vision extraction
                # Find the local file by matching filename substring
                local_path = None
                for fi in upload_files:
                    if fi["name"] in doc.file_path:
                        local_path = fi["path"]
                        break

                file_bytes = None
                if local_path and os.path.exists(local_path):
                    with open(local_path, "rb") as fh:
                        file_bytes = fh.read()

                try:
                    result = await extract_and_process_document(
                        db=db,
                        document_id=doc_id,
                        document_text="",  # Empty — extraction uses file_bytes for vision
                        file_bytes=file_bytes,
                    )
                    extraction_results.append(result)

                    status = result.get("status", "unknown")
                    items = result.get("items_extracted", 0)
                    processed = result.get("items_processed", 0)
                    errors = result.get("errors", [])

                    check(
                        f"  Extraction {fname} (status={status})",
                        status == "success",
                        "; ".join(errors) if errors else "",
                    )
                    print(f"    Items extracted: {items}, processed: {processed}")
                    if errors:
                        print(f"    Errors: {'; '.join(errors)}")

                    # Refresh doc to show final status
                    db.refresh(doc)
                    print(f"    DB extraction_status: {doc.extraction_status}")
                    print(f"    Document name: {doc.document_name}")
                    print(f"    Document category: {doc.document_category}")

                except Exception as e:
                    check(f"  Extraction {fname}", False, str(e))
                    logger.exception("Extraction error for doc %s", doc_id)

                # Delay between GPT calls to avoid rate limits
                await asyncio.sleep(2)

            print("\n  Extraction summary:")
            success = sum(1 for r in extraction_results if r.get("status") == "success")
            print(f"    Success: {success}/{len(extraction_results)}")
            total_items = sum(r.get("items_extracted", 0) for r in extraction_results)
            total_processed = sum(r.get("items_processed", 0) for r in extraction_results)
            print(f"    Total items extracted: {total_items}")
            print(f"    Total items processed: {total_processed}")

        # ===========================================================
        section("STEP 6 — VERIFY EXTRACTED DATA IN DB")
        # ===========================================================

        final_records = db.query(PreventiveRecord).filter(PreventiveRecord.pet_id == pet.id).all()
        print(f"\n  Preventive records after extraction ({len(final_records)}):")
        for r in final_records:
            iname = (r.preventive_master.item_name if r.preventive_master else
                     r.custom_preventive_item.item_name if r.custom_preventive_item else "?")
            if r.last_done_date:
                print(f"    • {iname}: last={r.last_done_date}, next={r.next_due_date}, status={r.status}")

        conditions = db.query(Condition).filter(Condition.pet_id == pet.id).all()
        print(f"\n  Conditions extracted ({len(conditions)}):")
        for c in conditions:
            print(f"    • {c.name} (type={c.condition_type}, active={c.is_active})")
            meds = db.query(ConditionMedication).filter(ConditionMedication.condition_id == c.id).all()
            for m in meds:
                print(f"        Medication: {m.name} {m.dose or ''} {m.frequency or ''}")
            monitors = db.query(ConditionMonitoring).filter(ConditionMonitoring.condition_id == c.id).all()
            for mon in monitors:
                print(f"        Monitor: {mon.name} ({mon.frequency or 'N/A'})")

        diag_results = db.query(DiagnosticTestResult).filter(DiagnosticTestResult.pet_id == pet.id).all()
        print(f"\n  Diagnostic test results ({len(diag_results)}):")
        for d in diag_results[:10]:  # Show first 10 to avoid wall of text
            val = d.value_text or (str(d.value_numeric) if d.value_numeric else "N/A")
            print(f"    • [{d.test_type}] {d.parameter_name} ({d.observed_at}): {val[:60]} [{d.status_flag}]")

        contacts = db.query(Contact).filter(Contact.pet_id == pet.id).all()
        print(f"\n  Contacts extracted ({len(contacts)}):")
        for c in contacts:
            print(f"    • {c.role}: {c.name} — {c.clinic_name}")

        final_docs = db.query(Document).filter(Document.pet_id == pet.id).all()
        print(f"\n  Documents in DB ({len(final_docs)}):")
        for d in final_docs:
            print(f"    • {d.document_name or os.path.basename(d.file_path)} "
                  f"[{d.document_category or 'uncategorized'}] "
                  f"status={d.extraction_status}")

        conflicts = (
            db.query(ConflictFlag)
            .join(PreventiveRecord, ConflictFlag.preventive_record_id == PreventiveRecord.id)
            .filter(PreventiveRecord.pet_id == pet.id)
            .all()
        )
        if conflicts:
            print(f"\n  Conflicts detected ({len(conflicts)}):")
            for cf in conflicts:
                rec = db.query(PreventiveRecord).filter(PreventiveRecord.id == cf.preventive_record_id).first()
                rname = (rec.preventive_master.item_name if rec and rec.preventive_master else
                         rec.custom_preventive_item.item_name if rec and rec.custom_preventive_item else "?")
                rec2 = db.query(PreventiveRecord).filter(PreventiveRecord.id == cf.preventive_record_id).first()
                existing = rec2.last_done_date if rec2 else "?"
                print(f"    • {rname}: existing={existing} vs new={cf.new_date} (status={cf.status})")

    except Exception as e:
        import traceback
        print(f"\n  FATAL ERROR: {e}")
        traceback.print_exc()
        FAIL += 1

    finally:
        db.close()

    # ===========================================================
    section("RESULTS")
    # ===========================================================
    print(f"\n  PASS: {PASS}")
    print(f"  FAIL: {FAIL}")
    print(f"  TOTAL: {PASS + FAIL}")
    print(f"\n  WhatsApp messages sent (mock): {len(_sent_messages)}")
    print()

    return FAIL


def main() -> int:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run())
    finally:
        loop.close()


if __name__ == "__main__":
    sys.exit(main())
