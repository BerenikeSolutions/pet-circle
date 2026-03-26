-- Migration 026: Breed Consequence Library
--
-- Static lookup table for breed-specific consequence text used in the
-- Overdue Insight (D+7+) reminder message:
--   "[Pet]'s [item] was due [X] days ago — [consequence_text]."
--
-- Populated for 15 named breeds across 8 reminder categories.
-- breed = 'Other' rows serve as generic fallback for any unlisted breed.
-- UNIQUE(breed, category) — one consequence per breed+category combo.
-- Safe to re-run: INSERT ... ON CONFLICT DO NOTHING.

BEGIN;

CREATE TABLE IF NOT EXISTS breed_consequence_library (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  breed            VARCHAR(100) NOT NULL,
  category         VARCHAR(50)  NOT NULL,
  consequence_text TEXT         NOT NULL,
  created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  UNIQUE (breed, category)
);

CREATE INDEX IF NOT EXISTS idx_breed_consequence_breed_category
  ON breed_consequence_library (breed, category);

-- ─────────────────────────────────────────────────
--  SEED DATA
-- ─────────────────────────────────────────────────
-- Categories: vaccine, deworming, flea_tick, food, supplement,
--             chronic_medicine, vet_followup, blood_checkup

INSERT INTO breed_consequence_library (breed, category, consequence_text) VALUES

-- ── Other (generic fallback for any unlisted breed) ──
('Other','vaccine','unvaccinated pets are at serious risk of preventable diseases that spread quickly'),
('Other','deworming','intestinal worms can cause weight loss, anaemia, and severe digestive issues if left untreated'),
('Other','flea_tick','flea infestations spread to the home and can cause skin infections and tick-borne diseases'),
('Other','food','running out of their regular food causes digestive upset and nutrient gaps'),
('Other','supplement','consistent supplementation is key — gaps reduce long-term joint and coat benefits'),
('Other','chronic_medicine','skipping chronic medication even briefly can cause flare-ups and worsen the condition'),
('Other','vet_followup','delayed vet follow-ups allow conditions to progress undetected and become harder to treat'),
('Other','blood_checkup','annual blood panels catch organ and metabolic issues years before symptoms appear'),

-- ── Golden Retriever ──
('Golden Retriever','vaccine','Goldens are prone to kennel cough and parvovirus — staying current is critical for this social breed'),
('Golden Retriever','deworming','Goldens love to explore outdoors, making them high-risk for picking up intestinal parasites'),
('Golden Retriever','flea_tick','Golden coats hide fleas easily — an untreated infestation can lead to hot spots and flea allergy dermatitis'),
('Golden Retriever','food','Goldens have a tendency to overeat — irregular food timing affects weight and joint health'),
('Golden Retriever','supplement','Goldens are genetically prone to hip dysplasia — joint supplements slow degeneration significantly'),
('Golden Retriever','chronic_medicine','this breed is sensitive to medication lapses — even one missed refill can destabilise management'),
('Golden Retriever','vet_followup','Golden Retrievers have one of the highest cancer rates among breeds — early vet check-ins are lifesaving'),
('Golden Retriever','blood_checkup','Goldens are prone to hypothyroidism and liver issues that only blood panels catch early'),

-- ── Labrador Retriever ──
('Labrador Retriever','vaccine','Labs socialise constantly — unvaccinated Labs put every dog they meet at risk'),
('Labrador Retriever','deworming','Labs'' love of eating anything off the ground makes regular deworming non-negotiable'),
('Labrador Retriever','flea_tick','Labs'' dense double coats make early flea detection difficult — prevention is far easier than treatment'),
('Labrador Retriever','food','Labs are prone to obesity; late reorders disrupt portion discipline and weight management'),
('Labrador Retriever','supplement','joint care from an early age is critical for Labs who are predisposed to elbow and hip dysplasia'),
('Labrador Retriever','chronic_medicine','Labs can mask discomfort well — missing medicine refills often goes unnoticed until a flare-up occurs'),
('Labrador Retriever','vet_followup','Labs are prone to ear infections and skin issues that worsen quickly without follow-up care'),
('Labrador Retriever','blood_checkup','Labs are at higher risk for exercise-induced collapse and thyroid disorders detectable by blood tests'),

-- ── German Shepherd ──
('German Shepherd','vaccine','GSDs frequently interact with working dogs and community spaces — vaccination gaps create real exposure risk'),
('German Shepherd','deworming','GSDs are active outdoor dogs with high parasite exposure risk, especially in urban India'),
('German Shepherd','flea_tick','German Shepherds'' thick double coat makes flea infestations hard to spot until they''re severe'),
('German Shepherd','food','GSDs are prone to bloat — food schedule disruptions increase risk of gastric dilatation-volvulus'),
('German Shepherd','supplement','hip and elbow dysplasia is hereditary in GSDs — regular joint support from age 2 is essential'),
('German Shepherd','chronic_medicine','GSDs with degenerative myelopathy or allergies deteriorate noticeably within weeks without medication'),
('German Shepherd','vet_followup','GSD spinal and joint conditions require regular monitoring — delayed follow-ups accelerate decline'),
('German Shepherd','blood_checkup','GSDs are prone to exocrine pancreatic insufficiency (EPI) and kidney disease, both caught by blood work'),

-- ── Beagle ──
('Beagle','vaccine','Beagles are pack-oriented and love dog parks — vaccination is critical to protect the whole pack'),
('Beagle','deworming','Beagles'' nose-to-ground sniffing habit gives parasites easy entry — deworming every 3 months is essential'),
('Beagle','flea_tick','Beagles spend a lot of time outdoors and are highly susceptible to tick-borne diseases like ehrlichiosis'),
('Beagle','food','Beagles will overeat if given the chance — delayed food orders disrupt structured feeding and cause weight gain'),
('Beagle','supplement','Beagles are prone to intervertebral disc disease — omega-3 and joint supplements provide meaningful protection'),
('Beagle','chronic_medicine','Beagles hide illness well — missing medication for epilepsy or hypothyroidism causes rapid deterioration'),
('Beagle','vet_followup','Beagles commonly develop ear infections and cherry eye — routine follow-ups catch these early'),
('Beagle','blood_checkup','Beagles are predisposed to hypothyroidism and Factor VII deficiency, both identifiable through blood panels'),

-- ── Shih Tzu ──
('Shih Tzu','vaccine','Shih Tzus have compromised immune responses due to their flat faces — vaccination protection is vital'),
('Shih Tzu','deworming','small breeds like Shih Tzus are severely affected by parasite loads that larger dogs can tolerate'),
('Shih Tzu','flea_tick','Shih Tzus'' long, dense coats are ideal flea habitats — regular prevention prevents skin infections'),
('Shih Tzu','food','Shih Tzus need consistent diet to avoid hypoglycaemia — food delays can cause dangerously low blood sugar'),
('Shih Tzu','supplement','Shih Tzus are prone to renal dysplasia — kidney-support supplements help maintain organ function'),
('Shih Tzu','chronic_medicine','Shih Tzus with respiratory or eye conditions deteriorate rapidly without consistent medication'),
('Shih Tzu','vet_followup','Shih Tzus need regular eye and dental checks — neglect leads to corneal ulcers and tooth loss'),
('Shih Tzu','blood_checkup','Shih Tzus are prone to liver shunts and renal issues — early detection through blood tests is critical'),

-- ── Pomeranian ──
('Pomeranian','vaccine','Pomeranians'' small frames mean disease hits harder — keeping vaccines current is non-negotiable'),
('Pomeranian','deworming','Poms'' tiny size makes parasite-related anaemia a serious risk that worsens faster than in larger dogs'),
('Pomeranian','flea_tick','Pomeranians'' thick double coats can hide severe flea infestations — prevention is far safer than treatment'),
('Pomeranian','food','Pomeranians are prone to hypoglycaemia — missed meals or late food orders can trigger dangerous drops in blood sugar'),
('Pomeranian','supplement','Poms are prone to alopecia X and joint issues — coat and joint supplements make a measurable difference'),
('Pomeranian','chronic_medicine','Pomeranians with tracheal collapse or heart disease can deteriorate within days without medication'),
('Pomeranian','vet_followup','Poms are prone to dental disease and luxating patella — routine follow-ups prevent expensive interventions'),
('Pomeranian','blood_checkup','Pomeranians are at higher risk for hypoglycaemia and thyroid disorders detected only by blood tests'),

-- ── Rottweiler ──
('Rottweiler','vaccine','Rottweilers are particularly susceptible to parvovirus — even one missed booster creates serious risk'),
('Rottweiler','deworming','Rottweilers'' high physical activity and outdoor exposure makes quarterly deworming essential'),
('Rottweiler','flea_tick','Rottweilers'' dark coats make ticks nearly invisible — tick paralysis is a real risk without prevention'),
('Rottweiler','food','Rottweilers need precise nutrition for muscle maintenance — irregular feeding disrupts body composition'),
('Rottweiler','supplement','Rottweilers are prone to hip and elbow dysplasia — glucosamine support from year 2 is strongly recommended'),
('Rottweiler','chronic_medicine','Rottweilers with heart conditions (subaortic stenosis) can decompensate quickly without medication'),
('Rottweiler','vet_followup','Rottweilers have a high rate of osteosarcoma — regular follow-ups enable earlier detection'),
('Rottweiler','blood_checkup','Rottweilers are prone to hypothyroidism and Von Willebrand''s disease caught through routine panels'),

-- ── Siberian Husky ──
('Siberian Husky','vaccine','Huskies are active and social — vaccine gaps expose the entire dog park to preventable diseases'),
('Siberian Husky','deworming','Huskies roam widely and are at high exposure risk for roundworms and hookworms from soil contact'),
('Siberian Husky','flea_tick','Huskies'' thick undercoat makes ticks extremely hard to find — prevention is the only reliable strategy'),
('Siberian Husky','food','Huskies have a unique metabolism — food disruptions can cause rapid weight loss or nutrient deficiency'),
('Siberian Husky','supplement','Huskies are prone to hip dysplasia and progressive retinal atrophy — targeted supplements support both'),
('Siberian Husky','chronic_medicine','Huskies with autoimmune conditions deteriorate quickly without consistent immunosuppressants or other meds'),
('Siberian Husky','vet_followup','Huskies are prone to cataracts and laryngeal paralysis — regular eye and throat checks are important'),
('Siberian Husky','blood_checkup','Huskies carry a genetic predisposition to zinc-responsive dermatosis and thyroid issues found in blood work'),

-- ── Indian Dog (Indie) ──
('Indian Dog','vaccine','Indies are hardy but unvaccinated dogs in India face real risk from rabies, distemper, and parvovirus'),
('Indian Dog','deworming','Indies have often had street parasite exposure — keeping deworming regular protects their long-term gut health'),
('Indian Dog','flea_tick','Indies living in warm Indian climates face year-round tick exposure — prevention is critical, not seasonal'),
('Indian Dog','food','Indies thrive on routine — disrupted feeding schedules cause anxiety and digestive issues in this breed'),
('Indian Dog','supplement','rescued Indies often have nutritional gaps from early life — supplements bridge these deficiencies effectively'),
('Indian Dog','chronic_medicine','Indies are resilient but bounce back faster when chronic conditions are managed consistently'),
('Indian Dog','vet_followup','skin conditions and ear infections are common in Indies — early follow-ups prevent chronic complications'),
('Indian Dog','blood_checkup','Indies benefit from annual blood panels to detect tick-borne diseases like ehrlichiosis and babesiosis'),

-- ── Dachshund ──
('Dachshund','vaccine','Dachshunds'' love of digging exposes them to leptospirosis — keeping leptospira vaccine current is critical'),
('Dachshund','deworming','Dachshunds'' ground-hugging lifestyle means soil parasites are a constant risk'),
('Dachshund','flea_tick','Dachshunds'' long body close to the ground means maximum tick exposure on every walk'),
('Dachshund','food','Dachshunds are highly prone to obesity — consistent food supply is key to maintaining healthy spinal weight'),
('Dachshund','supplement','intervertebral disc disease (IVDD) is the #1 health risk for Dachshunds — spine supplements are essential'),
('Dachshund','chronic_medicine','Dachshunds with IVDD or Cushing''s disease decline rapidly if medication is disrupted'),
('Dachshund','vet_followup','spinal issues can progress rapidly in Dachshunds — routine follow-ups catch early disc problems'),
('Dachshund','blood_checkup','Dachshunds are prone to Cushing''s disease and diabetes mellitus, both detectable through blood work'),

-- ── French Bulldog ──
('French Bulldog','vaccine','Frenchies'' compromised airways make respiratory infections especially dangerous — vaccines are essential protection'),
('French Bulldog','deworming','French Bulldogs'' brachycephalic stress means a parasite load hits them harder and faster than other breeds'),
('French Bulldog','flea_tick','Frenchies'' skin folds are prime flea hiding spots — regular prevention protects their sensitive skin'),
('French Bulldog','food','French Bulldogs are prone to food allergies and obesity — late food reorders disrupt their sensitive diet'),
('French Bulldog','supplement','Frenchies need joint support early — their compact structure puts above-average stress on hips and spines'),
('French Bulldog','chronic_medicine','French Bulldogs with respiratory or skin conditions worsen quickly without consistent medical management'),
('French Bulldog','vet_followup','Frenchies need regular checks for brachycephalic obstructive airway syndrome (BOAS) and skin fold dermatitis'),
('French Bulldog','blood_checkup','French Bulldogs have elevated risk for thyroid dysfunction and hereditary cataracts found through early screening'),

-- ── Samoyed ──
('Samoyed','vaccine','Samoyeds are naturally social and love interacting with other dogs — vaccination keeps every interaction safe'),
('Samoyed','deworming','Samoyeds'' outdoor enthusiasm makes them frequent candidates for parasitic infections in parks and trails'),
('Samoyed','flea_tick','Samoyed''s thick white coat is a perfect flea habitat — infestations are nearly invisible until severe'),
('Samoyed','food','Samoyeds have sensitive digestive systems — food disruptions cause diarrhoea and nutritional imbalances'),
('Samoyed','supplement','Samoyeds are prone to diabetes mellitus and hip dysplasia — targeted supplements support both conditions'),
('Samoyed','chronic_medicine','Samoyeds with diabetes or hereditary nephritis deteriorate rapidly without consistent medication management'),
('Samoyed','vet_followup','Samoyed hereditary glomerulopathy (kidney disease) requires regular monitoring — follow-ups detect changes early'),
('Samoyed','blood_checkup','Samoyeds have a genetic predisposition to kidney disease and diabetes — blood panels are the earliest warning system'),

-- ── Shiba Inu ──
('Shiba Inu','vaccine','Shibas are independent roamers — ensuring vaccine coverage protects them and every dog they encounter'),
('Shiba Inu','deworming','Shibas'' cat-like outdoor habits expose them to parasites — consistent deworming is essential'),
('Shiba Inu','flea_tick','Shibas spend significant time outdoors — tick-borne diseases are a serious concern in India'),
('Shiba Inu','food','Shibas are known for food pickiness — late reorders can disrupt the routine they depend on'),
('Shiba Inu','supplement','Shibas are prone to glaucoma and allergies — targeted supplements help manage both conditions over time'),
('Shiba Inu','chronic_medicine','Shibas with allergic skin disease (atopy) flare severely when medication consistency is broken'),
('Shiba Inu','vet_followup','Shibas are prone to glaucoma — regular eye pressure checks catch this painful condition early'),
('Shiba Inu','blood_checkup','Shibas carry elevated risk for GM1 gangliosidosis and hypothyroidism detectable through genetic and blood panels'),

-- ── Poodle ──
('Poodle','vaccine','Poodles are social and excel in training environments — vaccine protection is essential for group settings'),
('Poodle','deworming','Poodles'' love of play in parks and outdoor spaces makes regular deworming a consistent need'),
('Poodle','flea_tick','Poodle coats are dense and curly — fleas and ticks hide deep inside and are missed without prevention'),
('Poodle','food','Poodles are prone to GDV (bloat) — consistent feeding schedule and diet are critical for this deep-chested breed'),
('Poodle','supplement','Poodles are prone to Addison''s disease and joint issues — targeted supplements complement medical management'),
('Poodle','chronic_medicine','Poodles with Addison''s disease or epilepsy can suffer acute crises if medication schedules are disrupted'),
('Poodle','vet_followup','Poodles are prone to progressive retinal atrophy — annual eye exams and vet follow-ups are essential'),
('Poodle','blood_checkup','Poodles have elevated risk for Addison''s disease, thyroid disorders, and haemolytic anaemia found through blood tests'),

-- ── Bernese Mountain Dog ──
('Bernese Mountain Dog','vaccine','Berners have a shortened lifespan compared to other large breeds — protecting what time they have is vital'),
('Bernese Mountain Dog','deworming','Berners'' large frames mask parasite impact longer — by the time symptoms show, the load is already high'),
('Bernese Mountain Dog','flea_tick','Berners'' thick tri-colour coats provide excellent cover for ticks — prevention is the only reliable approach'),
('Bernese Mountain Dog','food','Berners'' size means food runs out faster — delayed reorders leave a large active dog under-fed'),
('Bernese Mountain Dog','supplement','Berners are the most joint-affected large breed — glucosamine and fish oil supplementation from age 1 is critical'),
('Bernese Mountain Dog','chronic_medicine','Berners with degenerative conditions decline noticeably faster than other breeds when medication is disrupted'),
('Bernese Mountain Dog','vet_followup','histiocytic sarcoma is uniquely common in Berners — early detection at regular vet visits can be lifesaving'),
('Bernese Mountain Dog','blood_checkup','Berners have one of the highest cancer rates of any breed — routine blood panels detect early markers')

ON CONFLICT (breed, category) DO NOTHING;

COMMIT;
