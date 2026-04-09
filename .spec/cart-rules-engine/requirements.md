# Requirements: Cart Rules Engine

## Introduction

PetCircle's care plan currently shows an "Order Now" CTA that links to a basic cart with no intelligence about what the user actually feeds their pet. The Cart Rules Engine replaces this with a signal-level resolution system: the more the system knows about a pet's diet (brand, product line, pack size, health conditions, breed), the more precisely it pre-selects products. This feature also replaces the existing product catalog with a new structured Food + Supplements database (41 SKUs), and rebuilds the product selector UX as an inline card that opens from the care plan.

Primary users: pet parents accessing the dashboard via tokenized links; the system itself (automated signal detection from WhatsApp conversation data and care plan records).

---

## Requirements

### Requirement 1: Product Database Rebuild

**User Story:** As a system operator, I want the product catalog rebuilt with structured Food and Supplement SKUs so that cart resolution can query by brand, product line, pack size, condition, breed, and life stage.

#### Acceptance Criteria

1. WHEN the migration runs THEN the system SHALL drop the existing `product_catalog` table and create two new tables: `product_food` (25 rows) and `product_supplement` (16 rows).
2. The `product_food` table SHALL contain columns: `sku_id` (PK, VARCHAR), `brand_id`, `brand_name`, `product_line`, `life_stage`, `breed_size`, `pack_size_kg` (DECIMAL), `mrp` (INTEGER, Rs.), `discounted_price` (INTEGER, Rs.), `condition_tags` (TEXT -- comma-separated), `breed_tags` (TEXT -- comma-separated), `vet_diet_flag` (BOOLEAN), `active` (BOOLEAN), `popularity_rank` (INTEGER), `monthly_units_sold` (INTEGER), `price_per_kg` (INTEGER, Rs.), `in_stock` (BOOLEAN), `notes` (TEXT), `created_at` (TIMESTAMP).
3. The `product_supplement` table SHALL contain columns: `sku_id` (PK, VARCHAR), `brand_id`, `brand_name`, `product_name`, `type` (VARCHAR -- fish_oil, joint_supplement, multivitamin, etc.), `form` (VARCHAR -- liquid, chew, powder, paste, tablet), `pack_size` (VARCHAR), `mrp` (INTEGER, Rs.), `discounted_price` (INTEGER, Rs.), `key_ingredients` (TEXT), `condition_tags` (TEXT -- comma-separated), `life_stage_tags` (TEXT -- comma-separated), `active` (BOOLEAN), `popularity_rank` (INTEGER), `monthly_units` (INTEGER), `price_per_unit` (INTEGER, Rs.), `in_stock` (BOOLEAN), `notes` (TEXT), `created_at` (TIMESTAMP).
4. WHEN the seed script runs THEN it SHALL populate `product_food` with exactly 25 rows (F001-F025) and `product_supplement` with exactly 16 rows (S001-S016) matching the Excel data verbatim.
5. The system SHALL update all foreign key references from `cart_items.product_id` to resolve against the new `sku_id` fields in either table.
6. IF the migration is applied to a database with existing orders THEN those orders SHALL remain intact (orders use free-text `items_description`, not FK to product_catalog).

---

### Requirement 2: Signal Level Detection

**User Story:** As the cart system, I want to determine the signal level (L5-L1) for each diet/supplement item in a pet's care plan so that the correct product resolution rule is applied.

#### Acceptance Criteria

1. The system SHALL classify every food item into exactly one of six levels: L5 (Exact SKU), L4 (Product Known, Size Unknown), L3 (Brand Known, Line Unknown), L2 (Category + Profile Known), L2b (Breed-Specific), L1 (No Data).
2. The system SHALL classify every supplement item into exactly one of four levels: L5 (Exact SKU), L4 (Brand + Type Known, Size Unknown), L3 (Type Known, Brand Unknown), L1 (Generic Mention).
3. WHEN determining signal level THEN the system SHALL read signals in priority order: Brand > Product Line > Pack Size > Health Condition > Breed > Life Stage, and assign the highest matching level.
4. Signal data SHALL be derived from: `diet_items` table (brand, product name fields), `pet` profile (breed, DOB -> life stage, weight), `conditions` table (active conditions), and `pet_preferences` table (prior purchase history).
5. IF multiple signal levels could apply THEN the system SHALL select the highest (most specific) level.

---

### Requirement 3: Food Cart Resolution Rules (A1-A6)

**User Story:** As a pet parent, I want the "Order Now" button to show me the most relevant food products based on what the system knows about my pet's diet so that I can reorder quickly.

#### Acceptance Criteria

**A1 -- L5 Exact SKU:**
1. WHEN brand + product line + pack size are all known THEN the system SHALL display the exact matching SKU pre-selected with qty=1, plus up to 2 alternative pack sizes of the same product line.
2. IF the exact pack size is not found in the DB THEN the system SHALL show the nearest available pack size and flag the difference to the user.

**A2 -- L4 Product Known, Size Unknown:**
3. WHEN brand + product line are known but pack size is not THEN the system SHALL display a pack-size selector showing all active pack sizes for that product line, sorted by `popularity_rank`.
4. The system SHALL display price per kg for each size option and highlight the most popular size.
5. The system SHALL show a maximum of 3 size options.

**A3 -- L3 Brand Known, Line Unknown:**
6. WHEN only the brand is known THEN the system SHALL show up to 3 product lines from that brand relevant to the pet's profile.
7. Product lines SHALL be ranked by: health_condition match > life_stage match > breed_match > popularity_rank.

**A4 -- L2 Category + Profile Known:**
8. WHEN food type (kibble/wet) is known along with life stage, breed size, or health condition THEN the system SHALL show top 3 brands with the single most relevant product per brand.
9. Products SHALL be ranked by: condition_match > life_stage > breed_size > popularity_rank.

**A5 -- L2b Breed-Specific:**
10. WHEN breed is known but no health condition is present THEN the system SHALL show breed-specific product lines first (matching `breed_tags`).
11. IF no breed-specific SKU exists THEN the system SHALL fall back to the matching breed size category (large/medium/small).
12. The system SHALL show a maximum of 3 options.

**A6 -- L1 No Data:**
13. WHEN only "food" is mentioned with no brand, type, or profile data THEN the system SHALL NOT show an "Order Now" CTA.
14. The system SHALL display the item as text-only in the Continue section and trigger a WhatsApp prompt to collect brand/type details.

---

### Requirement 4: Supplement Cart Resolution Rules (B1-B4)

**User Story:** As a pet parent, I want supplement recommendations based on what the system knows about the supplements I give my pet.

#### Acceptance Criteria

**B1 -- L5 Exact SKU:**
1. WHEN brand + supplement type + variant/form + pack size are all known THEN the system SHALL add the exact SKU directly to cart with qty=1.
2. IF the exact variant is not found THEN the system SHALL show the closest variant and notify the user.

**B2 -- L4 Brand + Type Known, Size Unknown:**
3. WHEN brand + supplement type are known but pack size is not THEN the system SHALL show pack size options with price per unit, default-selecting the most popular.
4. The system SHALL show a maximum of 3 size options.

**B3 -- L3 Type Known, Brand Unknown:**
5. WHEN only the supplement type is known (e.g., "fish oil") THEN the system SHALL show the top 3 brands for that type.
6. Brands SHALL be ranked by: popularity_rank ASC (bestsellers first), with the composition being 2 bestsellers + 1 budget option (lowest price).
7. IF fewer than 3 brands exist for that type THEN the system SHALL show all available brands.

**B4 -- L1 Generic Mention:**
8. WHEN only "supplements" or "vitamins" is mentioned without type or brand THEN the system SHALL NOT show an "Order Now" CTA.
9. The system SHALL trigger an info-capture prompt via WhatsApp to collect the supplement name.

---

### Requirement 5: Cart UX Rules (C1-C8)

**User Story:** As a pet parent, I want a consistent, trustworthy cart experience across all signal levels.

#### Acceptance Criteria

**C1 -- Quantity Default:**
1. The system SHALL always default quantity to 1. The system SHALL never auto-set quantity greater than 1.

**C2 -- Out of Stock:**
2. The system SHALL NOT show out-of-stock products (`in_stock = FALSE`) as the primary recommendation.
3. WHEN all matching products are OOS THEN the system SHALL show the nearest alternative that is in stock.

**C3 -- Price Display:**
4. The system SHALL always display: unit price (price per kg or price per unit), pack size, and MRP vs discounted price where a discount exists.

**C4 -- WhatsApp Confirmation:**
5. WHEN an order is placed THEN the system SHALL send a WhatsApp message: "Your [Product Name] for [Pet Name] has been ordered! Expected delivery: [date]."

**C5 -- Vet Diet Flag:**
6. IF a product has `vet_diet_flag = TRUE` THEN the system SHALL display a disclaimer: "This is a therapeutic diet. Please use under veterinary guidance."
7. The system SHALL NOT block the purchase of vet diet products.

**C6 -- Cart Persistence:**
8. Cart state SHALL persist for 72 hours.
9. IF a user returns within 72 hours with items in cart THEN the system SHALL show: "Resume your order for [Pet Name]?"

**C7 -- Pack Size Recommendation:**
10. WHEN pack size is unknown (L4 level) AND the pet's weight is known THEN the system SHALL highlight the pack size that best matches the pet's weight-based monthly consumption (e.g., 30kg dog eating ~300g/day -> suggest ~9kg bag).

**C8 -- Max Options:**
11. The system SHALL never show more than 3 product options at any signal level. IF more than 3 results match THEN the system SHALL rank and trim to the top 3.

---

### Requirement 6: Product Selector Card UX

**User Story:** As a pet parent, I want to see product options in a compact card when I tap "Order Now" so that I can quickly select and add to cart without leaving the care plan.

#### Acceptance Criteria

1. WHEN the user taps "Order Now" on a care plan item THEN a product selector card SHALL open inline.
2. The card SHALL display: product options (as per signal level rules), quantity selector, and pricing information per rule C3.
3. The topmost product option SHALL be pre-selected with qty = 1.
4. The user SHALL be able to change quantity and select a different SKU within the card.
5. The card SHALL have two bottom buttons: "Add to cart" (right) and "Search more" (left).
6. For the initial focus group release, the "Search more" button SHALL be hidden.
7. WHEN the user taps "Add to cart" THEN the item SHALL be added to the cart and the card SHALL close, returning the user to the care plan.
8. The card SHALL have a cancel (x) button in the top right corner.
9. The final Cart/Order page SHALL have a search bar at the top to allow the user to search any product and add to cart.

---

### Requirement 7: Signal-Aware Care Plan Integration

**User Story:** As a pet parent viewing my care plan, I want the "Order Now" CTA to appear only when the system has enough data to show relevant products, and to see contextual prompts when data is insufficient.

#### Acceptance Criteria

1. WHEN a care plan diet/supplement item has signal level L2 or higher THEN the system SHALL show an "Order Now ->" CTA button.
2. WHEN a care plan item has signal level L1 (no data) THEN the system SHALL NOT show an "Order Now" CTA and SHALL display the item as text-only.
3. WHEN signal level is L1 THEN the system SHALL surface a prompt in the care plan Continue section encouraging the user to share more details via WhatsApp.
4. The system SHALL re-evaluate signal levels whenever pet profile data, diet items, conditions, or preferences are updated.

---

### Requirement 8: Backward Compatibility

**User Story:** As a system operator, I want the new cart rules engine to work with existing orders, cart items, and preferences without data loss.

#### Acceptance Criteria

1. Existing rows in `orders` SHALL remain intact after migration (they use free-text `items_description`).
2. Existing rows in `cart_items` SHALL be cleared during migration (stale references to old product_catalog).
3. Existing `pet_preferences` records SHALL remain intact.
4. The `order_recommendations` table SHALL be cleared (cached recommendations reference old product IDs).
5. IF the agentic order flow (`agentic_order.py`) references product_catalog THEN those references SHALL be updated to use the new tables.
6. The WhatsApp order flow (`order_service.py`) SHALL continue to function, using signal-level resolution for product suggestions instead of AI-only recommendations.

---

### Design Decisions (resolved from open questions)

- **GPT vs Deterministic:** Deterministic signal resolution is primary. GPT fallback only when no products match at any level above L1.
- **cart_items.product_id:** Will store the new `sku_id` (e.g., "F001", "S003") directly as VARCHAR.
