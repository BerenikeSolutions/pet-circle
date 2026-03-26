-- Migration 025: Nudge Message Library
--
-- Central library for all WhatsApp nudge message content.
-- The nudge_scheduler service reads from this table to select the right message
-- for each user's current level, slot, and breed.
--
-- Columns:
--   level         — 0 (Cold Start), 1 (Breed, no records), 2 (Breed + records)
--   slot_day      — O+N day (1, 5, 10, 20, 30) or 0 for post-30 cycling
--   seq           — sequence within same level+slot_day+message_type+breed
--   message_type  — value_add | engagement_only | breed_only | breed_data
--   breed         — 'All' for non-breed-specific; specific breed name otherwise
--   category      — NULL for non-L2; data category for breed_data (L2) messages
--   template_key  — env var name of the WA template to use
--   template_var_1 to _4 — content for WA template {{1}}–{{4}} variables
--                  pet_name is always fetched at send time from DB — not stored here
--
-- Template mapping:
--   value_add         → WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL
--                        {{1}} = pet_name (from DB), {{2}} = template_var_1 (tip text)
--   engagement_only   → WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT
--                        {{1}} = template_var_1 (breed_context), {{2}} = template_var_2 (cta)
--   breed_only        → WHATSAPP_TEMPLATE_NUDGE_BREED
--                        {{1}} = template_var_1 (breed_insight), {{2}} = template_var_2 (cta)
--   breed_data        → WHATSAPP_TEMPLATE_NUDGE_BREED_DATA
--                        {{1}} = template_var_1 (breed_insight), {{2}} = pet_name (from DB)
--                        {{3}} = template_var_3 (record_type), {{4}} = template_var_4 (reply_action)
--
-- Safe to re-run: INSERT ... ON CONFLICT DO NOTHING.

BEGIN;

CREATE TABLE IF NOT EXISTS nudge_message_library (
  id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  level          INTEGER      NOT NULL CHECK (level IN (0, 1, 2)),
  slot_day       INTEGER      NOT NULL DEFAULT 0,  -- 0 = post-30 cycling
  seq            INTEGER      NOT NULL DEFAULT 1,   -- order within same level+slot+type+breed
  message_type   VARCHAR(30)  NOT NULL CHECK (message_type IN ('value_add','engagement_only','breed_only','breed_data')),
  breed          VARCHAR(100) NOT NULL DEFAULT 'All',
  category       VARCHAR(50),                       -- for breed_data L2 messages
  template_key   VARCHAR(100) NOT NULL,             -- env var name
  template_var_1 TEXT,
  template_var_2 TEXT,
  template_var_3 TEXT,
  template_var_4 TEXT,
  notes          TEXT,
  created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  UNIQUE (level, slot_day, seq, message_type, breed)
);

CREATE INDEX IF NOT EXISTS idx_nudge_library_level_slot
  ON nudge_message_library (level, slot_day, message_type, breed);

CREATE INDEX IF NOT EXISTS idx_nudge_library_l2_category
  ON nudge_message_library (level, category, breed)
  WHERE level = 2;

-- ─────────────────────────────────────────────────────────────────────────────
--  LEVEL 0 — Cold Start (no breed, no health data)
--  Message type: value_add | Template: WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL
--  {{1}} = pet_name (from DB), {{2}} = template_var_1 (the tip)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO nudge_message_library (level, slot_day, seq, message_type, breed, template_key, template_var_1, notes) VALUES
(0, 1,  1, 'value_add', 'All', 'WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL',
 'Did you know that preventive care — vaccines, deworming, and annual checkups — reduces your pet''s risk of serious illness by over 60%? A little consistency goes a long way.',
 'L0 O+1 — general preventive care tip'),
(0, 5,  1, 'value_add', 'All', 'WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL',
 'Most pet parents don''t realise that dental disease affects 80% of dogs over age 3. Brushing 3× a week or offering dental chews significantly reduces tartar buildup and bad breath.',
 'L0 O+5 — dental health tip'),
(0, 10, 1, 'value_add', 'All', 'WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL',
 'Hydration matters more than most owners think. Pets on dry food diets need 60–70ml of water per kg of body weight daily. A water fountain can increase intake by up to 50%.',
 'L0 O+10 — hydration tip'),
(0, 20, 1, 'value_add', 'All', 'WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL',
 'Flea and tick prevention works best when it''s year-round — not just in summer. In India''s warm climate, parasites are active in every season. Monthly prevention is the gold standard.',
 'L0 O+20 — parasite prevention tip (new)'),
(0, 30, 1, 'value_add', 'All', 'WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL',
 'Annual blood tests are one of the most underused tools in pet health. They catch kidney disease, thyroid disorders, and diabetes years before symptoms appear — when treatment is most effective.',
 'L0 O+30 — blood test / early detection tip (new)'),
(0, 0,  1, 'value_add', 'All', 'WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL',
 'A healthy weight is the single biggest factor in your pet''s joint health and lifespan. You should be able to feel (but not see) their ribs. Ask your vet about the ideal weight range.',
 'L0 post-30 cycling — weight and joint health tip')
ON CONFLICT (level, slot_day, seq, message_type, breed) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
--  LEVEL 1 — Breed available, no health records
--  Non-breed slots use value_add; breed slots use engagement_only or breed_only
-- ─────────────────────────────────────────────────────────────────────────────

-- O+1 and O+10: value_add (same generic tips, breed='All')
INSERT INTO nudge_message_library (level, slot_day, seq, message_type, breed, template_key, template_var_1, notes) VALUES
(1, 1,  1, 'value_add', 'All', 'WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL',
 'Setting up a complete health record in PetCircle means you''ll never miss a vaccine, deworming, or vet follow-up again. Your pet''s health history in one place — ready whenever you need it.',
 'L1 O+1 — value add: profile completion nudge'),
(1, 10, 1, 'value_add', 'All', 'WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL',
 'Pets with a documented health history get faster, more accurate diagnoses at the vet. Uploading past records takes 2 minutes and can make a big difference in an emergency.',
 'L1 O+10 — value add: record upload benefit')
ON CONFLICT (level, slot_day, seq, message_type, breed) DO NOTHING;

-- ── O+5 and O+20: Engagement Only — breed-specific insights ──
-- Template: WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT
-- {{1}} = template_var_1 (breed_context), {{2}} = template_var_2 (cta_question)

INSERT INTO nudge_message_library (level, slot_day, seq, message_type, breed, template_key, template_var_1, template_var_2, notes) VALUES

-- Golden Retriever
(1, 5,  1, 'engagement_only', 'Golden Retriever', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Golden Retrievers were originally bred as hunting dogs to retrieve waterfowl — their love of carrying things in their mouths is pure instinct, not just a habit!',
 'Does your Golden have a favourite thing to carry around the house? 😄', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Golden Retriever', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Goldens are one of the most emotionally intelligent breeds — studies show they can identify when their owner is stressed and actively try to comfort them.',
 'Has your Golden ever comforted you during a tough day? 🐾', 'L1 O+20'),

-- Labrador Retriever
(1, 5,  1, 'engagement_only', 'Labrador Retriever', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Labrador Retrievers have a double coat that repels water — making them exceptional swimmers even in cold conditions. Their love of water is hardwired, not trained.',
 'Does your Lab go crazy near water? 🏊 Tell us their funniest water story!', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Labrador Retriever', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Labs have a gene mutation (POMC) that affects how they feel full — which is why they''re almost always hungry and motivated by food. It''s not greed, it''s genetics!',
 'Is your Lab a bottomless pit when it comes to food? 😂', 'L1 O+20'),

-- German Shepherd
(1, 5,  1, 'engagement_only', 'German Shepherd', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'German Shepherds have a nose with 225 million scent receptors compared to a human''s 5 million. They can detect a teaspoon of sugar dissolved in a million gallons of water.',
 'Has your GSD ever sniffed out something you couldn''t find? 🔍', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'German Shepherd', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'GSDs are one of the few breeds that understand human pointing gestures intuitively — a skill even chimpanzees struggle with. They literally read your mind through your hands.',
 'Does your GSD follow your pointing or gestures perfectly? 🤯', 'L1 O+20'),

-- Beagle
(1, 5,  1, 'engagement_only', 'Beagle', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Beagles have one of the finest noses in the dog world — 220 million scent receptors. Their nose is so reliable that US Customs uses Beagles to sniff out illegal food at airports.',
 'Does your Beagle disappear into sniffing mode on every walk? 👃', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Beagle', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Beagles are pack animals at heart and can experience genuine separation anxiety when left alone. They were bred to work in groups and thrive on company — human or canine.',
 'Does your Beagle howl or act out when left alone? 🐕', 'L1 O+20'),

-- Shih Tzu
(1, 5,  1, 'engagement_only', 'Shih Tzu', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Shih Tzus were bred exclusively as royal companion dogs in ancient China and Tibet — they never had any working role. Relaxing on laps is quite literally in their DNA.',
 'Is your Shih Tzu a professional lap-warmer? ☕', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Shih Tzu', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Shih Tzus are one of the oldest dog breeds — DNA analysis shows they are genetically closest to the ancient wolf ancestor, making them a living link to dog prehistory.',
 'Does your ancient little Shih Tzu rule the household? 👑', 'L1 O+20'),

-- Pomeranian
(1, 5,  1, 'engagement_only', 'Pomeranian', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Pomeranians were originally large sled dogs in the Arctic. Queen Victoria fell in love with a small Pomeranian in Italy, and selectively bred them down to the pocket-sized version we know today.',
 'Does your mini sled dog still act like it''s pulling a team? ❄️', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Pomeranian', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Despite their small size, Pomeranians are bold, curious, and completely unaware they''re not the biggest dog in the room. This fearlessness is called "big dog syndrome."',
 'Has your Pom ever tried to take on a dog 10× their size? 😂', 'L1 O+20'),

-- Rottweiler
(1, 5,  1, 'engagement_only', 'Rottweiler', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Rottweilers were used by Roman legions to drive cattle across Europe. They''re one of the oldest herding breeds, and their calm, deliberate movement under pressure is a Roman legacy.',
 'Does your Rottie have that calm, steady energy that commands a room? 💪', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Rottweiler', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Rottweilers are deeply loyal and form a special bond with one primary person in the family — they often follow that person silently around the house, a behaviour called "shadowing."',
 'Does your Rottie have a favourite person they never let out of sight? 👀', 'L1 O+20'),

-- Siberian Husky
(1, 5,  1, 'engagement_only', 'Siberian Husky', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Huskies were bred by the Chukchi people of Siberia to run 100+ miles a day in -60°C conditions. Their metabolism is so efficient, they don''t tire the way other dogs do.',
 'Does your Husky have seemingly endless energy? 🏃 Tell us your exhausting stories!', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Siberian Husky', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Huskies are one of the most vocal dog breeds — they don''t typically bark, but they howl, talk, and woo in a remarkably human-like way. They genuinely seem to have opinions.',
 'Does your Husky talk back to you? 🗣️ Share their sassiest moment!', 'L1 O+20'),

-- Indian Dog (Indie)
(1, 5,  1, 'engagement_only', 'Indian Dog', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'The Indian Pariah Dog is one of the oldest dog breeds on Earth — genetically unchanged for over 15,000 years. Your Indie carries the DNA of the very first domesticated dogs.',
 'Does your ancient Indie have street-smart skills that never cease to amaze you? 🧠', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Indian Dog', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Indies have survived and thrived for millennia through natural selection — making them remarkably healthy, adaptable, and disease-resistant compared to most pedigree breeds.',
 'Has your Indie ever bounced back from something that surprised even the vet? 💪', 'L1 O+20'),

-- Dachshund
(1, 5,  1, 'engagement_only', 'Dachshund', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Dachshunds were bred in Germany to hunt badgers — their long bodies let them chase prey into burrows, while their loud bark alerted hunters above ground. The name literally means "badger dog."',
 'Does your Dachshund still dig, burrow, or bark like it''s on a hunt? 🦡', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Dachshund', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Dachshunds are disproportionately brave for their size — they were bred to face an animal three times their weight underground. Their stubbornness is actually ancient courage.',
 'Has your little warrior ever shown surprising bravery? 🏆', 'L1 O+20'),

-- French Bulldog
(1, 5,  1, 'engagement_only', 'French Bulldog', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Despite their name, French Bulldogs were actually created in England by lace workers, then brought to France during the Industrial Revolution. They''re technically English by origin!',
 'Does your Frenchie have more personality than most humans you know? 😄', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'French Bulldog', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'French Bulldogs are one of the top 5 most popular breeds globally — and they communicate entirely through a unique vocabulary of yawns, yips, and gargling sounds.',
 'Does your Frenchie have its own language? Share their most dramatic sound! 🎭', 'L1 O+20'),

-- Samoyed
(1, 5,  1, 'engagement_only', 'Samoyed', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Samoyeds were bred by the Samoyedic people of Siberia not just to sled, but to sleep inside the family tent at night — providing natural body heat in temperatures of -60°C.',
 'Does your Samoyed love sleeping close to the family? ❄️❤️', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Samoyed', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'The Samoyed''s perpetual "smile" is not just adorable — it''s functional. Their upturned lip corners prevent drool from freezing on their face in Arctic conditions.',
 'Does your Samoyed''s smile make strangers stop in the street? 😊', 'L1 O+20'),

-- Shiba Inu
(1, 5,  1, 'engagement_only', 'Shiba Inu', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Shiba Inus are ancient Japanese hunting dogs and one of the most primitive dog breeds — their independent, cat-like behaviour is thousands of years of selective breeding for self-sufficiency.',
 'Does your Shiba act more like a cat than a dog? 🐱', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Shiba Inu', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'The infamous "Shiba Scream" — a high-pitched wail Shibas emit when unhappy — can reach volumes comparable to a smoke alarm. It''s their way of expressing strong opinions.',
 'Has your Shiba ever unleashed the full scream on you? 😱', 'L1 O+20'),

-- Poodle
(1, 5,  1, 'engagement_only', 'Poodle', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Poodles are widely considered the second most intelligent dog breed in the world. The elaborate show clips were actually originally functional — protecting joints from cold water during duck hunts.',
 'Does your Poodle learn new tricks faster than you can teach them? 🎓', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Poodle', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Despite being ranked as a "hypoallergenic" breed, Poodles still produce the Fel d 1 protein that triggers allergies — they just shed far less, so allergen spread is much lower.',
 'Is your Poodle the reason an allergy-prone family member can have a dog? 🤧', 'L1 O+20'),

-- Bernese Mountain Dog
(1, 5,  1, 'engagement_only', 'Bernese Mountain Dog', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Bernese Mountain Dogs were working farm dogs in the Swiss Alps — used for herding cattle, pulling carts, and acting as watchdogs. Their calm, gentle giant personality is a direct result.',
 'Does your Berner have that special gentle-giant energy that melts everyone? 🏔️', 'L1 O+5'),
(1, 20, 1, 'engagement_only', 'Bernese Mountain Dog', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Berners have one of the shortest lifespans among large breeds — typically 7–10 years. This is why every wellness year counts more for them than almost any other breed.',
 'Do you make the most of every season with your Berner? 🍂', 'L1 O+20')

ON CONFLICT (level, slot_day, seq, message_type, breed) DO NOTHING;

-- ── O+30: Breed Only — breed-specific preventive care insight ──
-- Template: WHATSAPP_TEMPLATE_NUDGE_BREED
-- {{1}} = template_var_1 (breed_insight), {{2}} = template_var_2 (cta)

INSERT INTO nudge_message_library (level, slot_day, seq, message_type, breed, template_key, template_var_1, template_var_2, notes) VALUES
(1, 30, 1, 'breed_only', 'Golden Retriever',    'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Golden Retrievers have one of the highest cancer rates of any dog breed — nearly 60% are affected. Starting annual check-ups and blood panels from age 5 dramatically improves early detection.',
 'Has your Golden had a wellness blood test this year? 🩸', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Labrador Retriever',  'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Labrador Retrievers are the #1 breed affected by elbow and hip dysplasia. A joint supplement started at age 1–2 and weight management can delay the onset by years.',
 'Is your Lab''s joint care plan up to date? 💊', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'German Shepherd',     'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'German Shepherds are prone to degenerative myelopathy — a progressive spinal condition. Regular neurological monitoring and physical therapy started early significantly slow progression.',
 'Does your GSD have a routine mobility and spinal check scheduled? 🏃', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Beagle',              'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Beagles have one of the highest rates of hypothyroidism of any breed. Annual thyroid panels from age 4 allow early intervention before weight gain and lethargy set in.',
 'Has your Beagle had a thyroid check recently? 🔬', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Shih Tzu',            'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Shih Tzus are among the top breeds for renal dysplasia — a hereditary kidney condition. Early detection through annual kidney panels allows management before irreversible damage.',
 'Does your Shih Tzu have an annual kidney function check scheduled? 🫘', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Pomeranian',          'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Pomeranians are the breed most affected by tracheal collapse — a condition where the windpipe flattens under pressure. Keeping weight in check and using a harness instead of a collar is essential.',
 'Is your Pom on a harness and at a healthy weight? ⚖️', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Rottweiler',          'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Rottweilers have an elevated risk of osteosarcoma (bone cancer) — especially in the limbs. Any persistent lameness after age 5 warrants an X-ray, not just rest.',
 'Does your Rottie have an annual limb and joint X-ray on the schedule? 🦴', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Siberian Husky',      'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Siberian Huskies are the breed most commonly affected by hereditary cataracts. An annual eye exam from age 2 can detect this early, when management options are still available.',
 'Has your Husky had an eye health check this year? 👁️', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Indian Dog',          'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Indian Pariah Dogs are extraordinarily healthy due to natural selection — but tick-borne diseases like ehrlichiosis are a serious and underdiagnosed risk in India. Annual blood panels catch it early.',
 'Is your Indie''s tick prevention and annual blood test up to date? 🩸', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Dachshund',           'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Intervertebral disc disease (IVDD) affects 1 in 4 Dachshunds in their lifetime. Keeping weight below the ideal range and avoiding high-impact jumping reduces disc pressure significantly.',
 'Is your Dachshund''s weight in the healthy range for spinal protection? ⚖️', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'French Bulldog',      'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'French Bulldogs suffer from BOAS (Brachycephalic Obstructive Airway Syndrome) to varying degrees. An annual respiratory assessment scores their breathing and guides surgical decisions before a crisis.',
 'Has your Frenchie had a breathing assessment from a vet this year? 💨', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Samoyed',             'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Samoyeds carry a hereditary kidney disease (Samoyed Hereditary Glomerulopathy) that affects males more severely. Early urine protein testing catches kidney stress before it becomes irreversible.',
 'Does your Samoyed have annual kidney and urine health checks scheduled? 🫘', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Shiba Inu',           'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Shiba Inus are highly prone to allergic skin disease (canine atopy). Identifying triggers early — through allergy testing and elimination diets — prevents years of chronic skin flare-ups.',
 'Does your Shiba have recurrent itching or skin issues? 🐾', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Poodle',              'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Standard Poodles are disproportionately affected by Addison''s disease — a potentially fatal adrenal condition. It''s called the "Great Pretender" because it mimics other illnesses, making blood tests essential.',
 'Has your Poodle had an adrenal and electrolyte panel recently? 🔬', 'L1 O+30'),
(1, 30, 1, 'breed_only', 'Bernese Mountain Dog','WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Bernese Mountain Dogs have the highest rate of histiocytic sarcoma of any breed — a fast-moving cancer with a median survival of under 6 months from diagnosis. Annual imaging from age 5 improves outcomes.',
 'Is your Berner on an annual cancer screening plan? 🏥', 'L1 O+30')
ON CONFLICT (level, slot_day, seq, message_type, breed) DO NOTHING;

-- L1 fallback for unlisted breeds at O+30
INSERT INTO nudge_message_library (level, slot_day, seq, message_type, breed, template_key, template_var_1, template_var_2, notes) VALUES
(1, 5,  1, 'engagement_only', 'All', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Did you know dogs can sense changes in barometric pressure before a storm? Their acute hearing and sense of smell picks up what humans simply cannot detect.',
 'Has your pet ever predicted a storm before you knew one was coming? ⛈️', 'L1 O+5 fallback for unlisted breeds'),
(1, 20, 1, 'engagement_only', 'All', 'WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT',
 'Pets dream — research shows that dogs and cats have similar sleep cycles to humans, including REM sleep where the brain replays experiences and consolidates memory.',
 'Have you ever watched your pet dream? What do they do? 🌙', 'L1 O+20 fallback for unlisted breeds'),
(1, 30, 1, 'breed_only', 'All', 'WHATSAPP_TEMPLATE_NUDGE_BREED',
 'Every breed carries breed-specific health risks. Knowing yours and setting up proactive annual screening for those conditions gives your pet the best chance at a long, healthy life.',
 'Has your vet done a breed-specific health risk assessment for your pet? 🏥', 'L1 O+30 fallback for unlisted breeds')
ON CONFLICT (level, slot_day, seq, message_type, breed) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
--  LEVEL 2 — Breed + Data (slots 1–3)
--  Template: WHATSAPP_TEMPLATE_NUDGE_BREED_DATA
--  {{1}} = template_var_1 (breed_insight), {{2}} = pet_name (from DB),
--  {{3}} = template_var_3 (record_type label), {{4}} = template_var_4 (reply_action)
--
--  Data priority order: vaccine > flea_tick > deworming > nutrition >
--                       supplement > condition > medication > diagnostics > grooming
--  category column maps to this priority list.
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO nudge_message_library (level, slot_day, seq, message_type, breed, category, template_key, template_var_1, template_var_3, template_var_4, notes) VALUES

-- Golden Retriever — L2 breed_data per category
('2', 0, 1, 'breed_data', 'Golden Retriever', 'vaccine',    'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'Goldens are highly social and love dog parks — but that exposure makes up-to-date vaccines critical. Missing a booster puts your Golden and every dog they play with at risk.',
 'vaccination record', 'Reply with your Golden''s last vaccine date and we''ll set up reminders', 'L2 Golden vaccine'),
('2', 0, 1, 'breed_data', 'Golden Retriever', 'flea_tick',  'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'Goldens'' thick coats are ideal flea habitats. An untreated infestation quickly leads to flea allergy dermatitis — one of the most common (and preventable) skin conditions in this breed.',
 'flea & tick prevention', 'Let us know when prevention was last given and we''ll schedule the next one', 'L2 Golden flea'),
('2', 0, 1, 'breed_data', 'Golden Retriever', 'deworming',  'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'Goldens explore everything with their mouths — which makes regular deworming essential. A parasite load heavy enough to cause symptoms has usually been building for months.',
 'deworming record', 'Share your Golden''s last deworming date to keep this on track', 'L2 Golden deworming'),
('2', 0, 1, 'breed_data', 'Golden Retriever', 'nutrition',  'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'Golden Retrievers are prone to obesity, which significantly worsens hip dysplasia outcomes. Tracking daily food intake and pack size ensures portions stay consistent and reorders never run out.',
 'food details', 'Share your Golden''s current food brand and daily portion so we can track reorder timing', 'L2 Golden nutrition'),

-- Labrador Retriever — L2 breed_data
('2', 0, 1, 'breed_data', 'Labrador Retriever', 'vaccine',   'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'Labs socialise with dogs everywhere they go. A missed vaccine booster can silently leave them — and their playmates — unprotected against parvovirus and distemper.',
 'vaccination record', 'Share your Lab''s last vaccine date and we''ll keep reminders on track', 'L2 Lab vaccine'),
('2', 0, 1, 'breed_data', 'Labrador Retriever', 'flea_tick', 'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'Labs'' love of swimming and rolling in grass puts them in constant tick territory. Prevention given monthly ensures they never build up a dangerous parasite load.',
 'flea & tick prevention', 'Let us know the last prevention date and we''ll handle the reminders', 'L2 Lab flea'),
('2', 0, 1, 'breed_data', 'Labrador Retriever', 'deworming', 'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'Labs eat things they shouldn''t — regularly. Roundworms and hookworms are picked up easily and spread quietly until symptoms become hard to ignore.',
 'deworming record', 'Share your Lab''s last deworming date so we can schedule the next one', 'L2 Lab deworming'),

-- German Shepherd — L2 breed_data
('2', 0, 1, 'breed_data', 'German Shepherd', 'vaccine',   'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'GSDs often interact with working dogs, security environments, and community spaces — making complete vaccine coverage a matter of community health, not just personal protection.',
 'vaccination record', 'Share your GSD''s last vaccine date and we''ll track the full schedule', 'L2 GSD vaccine'),
('2', 0, 1, 'breed_data', 'German Shepherd', 'flea_tick', 'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'GSD''s double coat makes ticks almost impossible to spot by hand. Tick paralysis and ehrlichiosis are real risks for this active, outdoor-loving breed.',
 'flea & tick prevention', 'Share the last prevention date so we can keep this from lapsing', 'L2 GSD flea'),
('2', 0, 1, 'breed_data', 'German Shepherd', 'deworming', 'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'GSDs are active outdoor dogs with constant soil and environment contact. Quarterly deworming is especially important for this breed''s energy levels and gut health.',
 'deworming record', 'Let us know when your GSD was last dewormed and we''ll set the schedule', 'L2 GSD deworming'),

-- Generic L2 fallback for all other breeds
('2', 0, 1, 'breed_data', 'All', 'vaccine',    'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'Vaccines protect your pet from diseases that can spread in seconds at a park, vet clinic, or street. Staying current is the single most impactful thing you can do for long-term health.',
 'vaccination record', 'Share your pet''s last vaccine date and we''ll handle all the reminders from here', 'L2 All vaccine fallback'),
('2', 0, 1, 'breed_data', 'All', 'flea_tick',  'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'In India''s warm climate, ticks and fleas are active year-round — not just in summer. Monthly prevention is the gold standard, and it starts with knowing when the last treatment was given.',
 'flea & tick prevention', 'Share the last prevention date and we''ll schedule the next one automatically', 'L2 All flea fallback'),
('2', 0, 1, 'breed_data', 'All', 'deworming',  'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'Intestinal worms are common and often symptom-free until the load is high. A deworming schedule every 3 months is the most effective way to keep your pet''s gut healthy.',
 'deworming record', 'Let us know when your pet was last dewormed so we can keep this on track', 'L2 All deworming fallback'),
('2', 0, 1, 'breed_data', 'All', 'nutrition',  'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'Running out of your pet''s regular food causes digestive upset and nutrient gaps. Tracking pack size and daily portions means you''ll always get a reorder reminder before you run low.',
 'food & nutrition details', 'Share your pet''s current food brand and daily portion and we''ll track reorder timing', 'L2 All nutrition fallback'),
('2', 0, 1, 'breed_data', 'All', 'grooming',   'WHATSAPP_TEMPLATE_NUDGE_BREED_DATA',
 'Regular grooming isn''t just about appearance — it''s one of the best ways to catch lumps, skin issues, ear infections, and nail problems before they become serious.',
 'grooming schedule', 'Share your pet''s grooming routine and we''ll track it alongside their other care', 'L2 All grooming fallback')

ON CONFLICT (level, slot_day, seq, message_type, breed) DO NOTHING;

COMMIT;
