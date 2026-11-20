import base64
import os
import re
import json
import time
from typing import Dict, Any, Optional, List
from playwright.sync_api import sync_playwright
import pypdf

def sanitize_filename(name: str) -> str:
    """Removes invalid filesystem characters."""
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name)
    return sanitized.strip().replace(" ", "_")[:60]

def build_seo_filename(topic: str, keyword: str, angle_slug: str = "", vol_num: int = 1) -> str:
    """
    Constructs a 100% Google-optimized, hyphen-separated keyword filename without 'vol-1/2/3'.
    Matches target keyword or topic/title directly.
    Example: prodentim-review.pdf, nitric-boost-ultra-official-guide.pdf
    """
    k_clean = re.sub(r'[^a-zA-Z0-9\s-]', '', keyword or '').strip().lower()
    t_clean = re.sub(r'[^a-zA-Z0-9\s-]', '', topic or '').strip().lower()

    if k_clean:
        t_words = t_clean.split()
        k_words = k_clean.split()
        combined_words = []
        for w in t_words:
            if w not in combined_words:
                combined_words.append(w)
        for w in k_words:
            if w not in combined_words:
                combined_words.append(w)
        base_slug = "-".join(combined_words)[:60].rstrip("-")
    elif t_clean:
        base_slug = "-".join(t_clean.split())[:60].rstrip("-")
    else:
        base_slug = "document"

    angle_clean = re.sub(r'[^a-zA-Z0-9-]', '', angle_slug.lower() if angle_slug else "")[:25]

    # Only append angle if generating multiple angles (vol_num > 1) and angle is not already in slug
    if vol_num > 1 and angle_clean and angle_clean not in base_slug:
        base_slug = f"{base_slug}-{angle_clean}"

    return f"{base_slug}.pdf"

def hex_to_rgba(hex_code: str, alpha: float = 0.08) -> str:
    """Converts a hex color string to an rgba CSS string."""
    if not hex_code or not isinstance(hex_code, str):
        return f"rgba(30, 64, 175, {alpha})"
    c = hex_code.strip().lstrip("#")
    if len(c) == 3:
        c = "".join([x * 2 for x in c])
    if len(c) == 6:
        try:
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
            return f"rgba({r}, {g}, {b}, {alpha})"
        except Exception:
            pass
    return f"rgba(30, 64, 175, {alpha})"

def detect_category(topic: str, keyword: str, explicit_choice: str = "auto") -> str:
    """
    Intelligently detects product category or uses explicit user selection.
    Supported: 'health_supplements', 'tech_gadgets', 'lifestyle_goods', 'digital_software'
    """
    if explicit_choice and explicit_choice != "auto":
        return explicit_choice

    combined = f"{topic} {keyword}".lower()

    # Health / Supplements / Wellness keywords
    health_tokens = [
        "supplement", "capsule", "pill", "diet", "weight", "joint", "health", "cbd",
        "drop", "gumm", "skin", "serum", "cream", "vitamin", "formula", "detox",
        "muscle", "protein", "sleep", "blood", "vision", "gut", "tooth", "teeth",
        "dental", "probiotic", "collagen", "genesis", "puravive", "nagano", "sugar",
        "lean", "keto", "bioma", "slimming", "boost", "burn", "wellness", "doctor formulated"
    ]
    if any(t in combined for t in health_tokens):
        return "health_supplements"

    # Tech / Audio / Gadget keywords
    tech_tokens = [
        "headphone", "earphone", "earbud", "laptop", "phone", "audio", "battery",
        "keyboard", "mouse", "screen", "gadget", "watch", "camera", "tv", "speaker",
        "charger", "router", "cable", "monitor", "macbook", "sony", "iphone",
        "samsung", "noise cancel", "wireless", "bluetooth", "display", "processor"
    ]
    if any(t in combined for t in tech_tokens):
        return "tech_gadgets"

    # Digital / Software keywords
    soft_tokens = [
        "software", "app", "tool", "saas", "cloud", "course", "hosting", "vpn",
        "plugin", "theme", "membership", "license", "ai tool", "bot", "platform"
    ]
    if any(t in combined for t in soft_tokens):
        return "digital_software"

    # Default to physical consumer / lifestyle goods
    return "lifestyle_goods"

# 10 DEDICATED SEARCH-INTENT ARCHETYPES FOR 1 PRODUCT
ANGLE_ARCHETYPES = [
    {
        "id": "review",
        "angle_name": "In-Depth Review & Performance Test",
        "title_template": "{topic} Review: Ingredients, Evidence, Safety & Buying Guide",
        "meta_template": "Considering {topic}? Read our independent {keyword} guide evaluating verified ingredient claims, safety questions, real user results, and official pricing.",
        "focus_area": "Technical analysis, real testing, and evidence evaluation.",
        "keywords_type": "technical_review"
    },
    {
        "id": "buyer_guide",
        "angle_name": "The Ultimate 2026 Buyer's Guide",
        "title_template": "{topic} Complete Buyer's Guide: Specifications, Value & Decision Framework",
        "meta_template": "Thinking about buying {topic}? Our authoritative 2026 {keyword} guide breaks down practical utility, lifestyle integration, and essential considerations.",
        "focus_area": "Target personas, real-world utility, and buying decision frameworks.",
        "keywords_type": "commercial_guide"
    },
    {
        "id": "pros_cons",
        "angle_name": "Honest Pros, Cons & Hidden Flaws",
        "title_template": "{topic} Honest Breakdown: Standout Advantages, Real Flaws & Trade-Offs",
        "meta_template": "Before investing in {topic}, read our balanced investigation covering standout strengths, realistic trade-offs, and critical {keyword} considerations.",
        "focus_area": "Unbiased strengths and critical weaknesses for high reader trust.",
        "keywords_type": "pros_cons"
    },
    {
        "id": "comparison",
        "angle_name": "Competitor Comparison & Rival Benchmarks",
        "title_template": "{topic} vs Leading Competitors: Head-to-Head Comparison & Benchmark Guide",
        "meta_template": "How does {topic} stack up against leading alternatives? Detailed head-to-head comparison evaluating {keyword} performance, pricing, and overall value.",
        "focus_area": "Side-by-side rival analysis, category leadership, and benchmark tables.",
        "keywords_type": "comparison"
    },
    {
        "id": "value_deals",
        "angle_name": "Price, Deals & Long-Term Value Analysis",
        "title_template": "Is {topic} Worth the Money? Price Breakdown, Real ROI & Buying Guide",
        "meta_template": "Discover if {topic} justifies its price tag. We analyze long-term cost of ownership, official warranty protection, and current {keyword} discount deals.",
        "focus_area": "Commercial buying intent, return on investment, and merchant verification.",
        "keywords_type": "pricing_deals"
    },
    {
        "id": "durability",
        "angle_name": "Long-Term Durability & Ownership Report",
        "title_template": "{topic} Durability Report: Build Quality, Safety & Long-Term Results",
        "meta_template": "An exhaustive report on the build resilience, material quality, and verified customer satisfaction for {topic} under everyday {keyword} conditions.",
        "focus_area": "Wear and tear, material quality, and long-term customer satisfaction.",
        "keywords_type": "durability"
    },
    {
        "id": "lifestyle",
        "angle_name": "Practical Usability & Daily Workflow Integration",
        "title_template": "Living with {topic}: Everyday Routine, Best Practices & Real Results",
        "meta_template": "A practical report on everyday ownership of {topic}. Learn optimal usage guidelines, best practices, and essential facts for {keyword}.",
        "focus_area": "Ergonomics, daily routines, beginner setup, and practical hacks.",
        "keywords_type": "usability"
    },
    {
        "id": "mistakes_tips",
        "angle_name": "Expert Buying Tips & Common Mistakes to Avoid",
        "title_template": "Buying {topic}: 5 Critical Mistakes to Avoid and Expert Purchasing Tips",
        "meta_template": "Essential advice before purchasing {topic}. Avoid common counterfeit channels, warranty missteps, and improper purchasing traps in {keyword}.",
        "focus_area": "Preventing buyer regret, warranty verification, and authentic stock tips.",
        "keywords_type": "tips_mistakes"
    },
    {
        "id": "features_deepdive",
        "angle_name": "Core Technology & Engineering Breakdown",
        "title_template": "{topic} Deep Dive: Formulation, Core Specifications & Evidence",
        "meta_template": "A deep dive into the engineering, active components, and design decisions that make {topic} a leading option in {keyword}.",
        "focus_area": "Engineering architecture, component quality, and standout specifications.",
        "keywords_type": "tech_deepdive"
    },
    {
        "id": "final_verdict",
        "angle_name": "Final Conclusive Editorial Verdict",
        "title_template": "{topic} Conclusive Editorial Verdict: The Definitive Buying Decision",
        "meta_template": "Our definitive editorial verdict on {topic}. Summarizing benchmark results, key takeaways, and our official recommendation for {keyword}.",
        "focus_area": "Authoritative synthesis, final rating scores, and immediate action triggers.",
        "keywords_type": "editorial_verdict"
    }
]

def generate_unique_keywords_for_angle(keyword: str, topic: str, angle_type: str) -> List[str]:
    """Generates 20-25 distinct search keywords tailored to the specific search intent."""
    t_clean = re.sub(r'[-–|:•]\s*(?:text\s*presentation|video\s*presentation|presentation|vsl|official).*$', '', topic, flags=re.IGNORECASE).strip()
    t_clean = re.sub(r'\b(?:text|video)\s*presentation\b', '', t_clean, flags=re.IGNORECASE).strip()
    if not t_clean:
        t_clean = topic.strip()
    k_clean = keyword.strip()
    combo_kw = k_clean if t_clean.lower() in k_clean.lower() else f"{t_clean} {k_clean}"
    base_variants = [
        f"{t_clean}",
        f"{t_clean.lower()}",
        combo_kw,
        f"{t_clean} 2026",
        f"best {t_clean}",
        f"buy {t_clean} online",
        f"{t_clean} official price",
        f"{t_clean} official website"
    ]
    
    specific = []
    if angle_type == "technical_review":
        specific = [
            f"{t_clean} review", f"{t_clean} ingredients", f"{t_clean} supplement facts",
            f"{t_clean} in-depth review", f"{t_clean} real user results", f"{t_clean} customer reviews",
            f"{t_clean} does it work", f"{t_clean} clinical evidence", f"{t_clean} side effects",
            f"{t_clean} safety", f"{t_clean} refund policy", f"{t_clean} buying guide",
            f"is {t_clean} legit", f"{t_clean} complaints", f"{t_clean} dosage instructions",
            f"{t_clean} laboratory testing", f"{t_clean} genuine results", f"where to buy {t_clean}",
            f"{t_clean} cost per bottle"
        ]
    elif angle_type == "pros_cons":
        specific = [
            f"{t_clean} pros and cons", f"{t_clean} critical flaws", f"{t_clean} problems and issues",
            f"{t_clean} honest opinion", f"{t_clean} disadvantages", f"{t_clean} customer complaints",
            f"{t_clean} what they don't tell you", f"{t_clean} real drawbacks", f"{t_clean} reasons not to buy",
            f"{t_clean} common problems", f"{t_clean} worth the hype", f"{t_clean} hidden defects",
            f"{t_clean} honest user review", f"{t_clean} regrets buying", f"{t_clean} top benefits",
            f"{t_clean} standout advantages", f"{t_clean} is it overrated", f"{t_clean} unbiased feedback"
        ]
    elif angle_type == "comparison":
        specific = [
            f"{t_clean} vs competitors", f"{t_clean} comparison 2026", f"{t_clean} alternative options",
            f"{t_clean} vs leading rivals", f"{t_clean} head to head test", f"{t_clean} better than rivals",
            f"best alternative to {t_clean}", f"{t_clean} rival shootout", f"{t_clean} market comparison",
            f"{t_clean} value vs competitors", f"{t_clean} which is better", f"{t_clean} upgrade worth it",
            f"{t_clean} vs generic models", f"top rated rivals to {t_clean}", f"{t_clean} side by side comparison"
        ]
    elif angle_type == "pricing_deals":
        specific = [
            f"{t_clean} discount deal", f"{t_clean} best price online", f"{t_clean} sale 2026",
            f"{t_clean} price drop alert", f"{t_clean} value for money", f"{t_clean} worth the price",
            f"{t_clean} coupon code", f"cheapest place to buy {t_clean}", f"{t_clean} official discount",
            f"{t_clean} warranty protection", f"{t_clean} money back guarantee", f"{t_clean} bundle deals",
            f"{t_clean} genuine merchant deals", f"{t_clean} cost of ownership", f"{t_clean} authentic buyer deals"
        ]
    else:
        specific = [
            f"{t_clean} buyer guide", f"{t_clean} how to use", f"{t_clean} tips and tricks",
            f"{t_clean} maintenance guide", f"{t_clean} common mistakes", f"{t_clean} user manual tips",
            f"{t_clean} everyday experience", f"{t_clean} long term review", f"{t_clean} verified feedback",
            f"{t_clean} satisfaction rating", f"{t_clean} authorized seller", f"{t_clean} packaging details",
            f"{t_clean} unboxing review", f"{t_clean} where to buy safely"
        ]

    combined = base_variants + specific
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for item in combined:
        item_str = item.strip()
        if item_str.lower() not in seen:
            seen.add(item_str.lower())
            deduped.append(item_str)
    return deduped[:25]

def get_product_deep_research(topic: str, keyword: str, brand: str, category: str) -> Dict[str, Any]:
    t_lower = topic.lower()
    k_lower = keyword.lower()
    combined = f"{t_lower} {k_lower}"

    # 1. SLEEP & CIRCADIAN REGULATION (Yu Sleep, etc.)
    if any(w in combined for w in ["sleep", "insomnia", "circadian", "yu sleep", "rest", "melatonin", "night"]):
        return {
            "niche": "Sleep Architecture & Circadian Regulation",
            "format": "nano-enhanced liquid sublingual drops",
            "primary_benefit": "rapid sleep onset, restorative slow-wave delta sleep, and elimination of mid-night awakenings",
            "target_system": "circadian pacemaker (suprachiasmatic nucleus) and GABAergic inhibitory neurotransmission",
            "regulatory": "FDA-registered, GMP-certified laboratory in the United States adhering to strict USP purity standards",
            "hook_analogy": "Think of shopping for a sleep formula without investigating its clinical pharmacokinetics the same way you would pay full price at checkout when an unadvertised 70% manufacturer discount code was sitting right in front of you.",
            "ingredients": [
                {
                    "name": "Tart Cherry Extract (Prunus cerasus)",
                    "role": "Whole-Food Melatonin & Anthocyanins",
                    "mechanism": "Provides bio-identical phytomelatonin and concentrated proanthocyanidins that neutralize neuro-inflammatory cytokines linked to chronic nocturnal wakefulness.",
                    "evidence": "A double-blind, randomized crossover trial published in the European Journal of Nutrition documented statistically significant increases in total sleep time (+39 minutes) and sleep efficiency compared to placebo."
                },
                {
                    "name": "GABA (Gamma-Aminobutyric Acid)",
                    "role": "Primary Inhibitory Neurotransmitter",
                    "mechanism": "Binds to GABA-A neural receptors to down-regulate hyperarousal, reduce firing of excitatory neurons, and quiet nighttime mental chatter.",
                    "evidence": "Clinical pharmacokinetic research (2020–2024) indicates nano-emulsified sublingual delivery achieves up to 4.2x higher central bioavailability compared to traditional swallowed capsules."
                },
                {
                    "name": "5-HTP (5-Hydroxytryptophan)",
                    "role": "Direct Serotonin & Melatonin Precursor",
                    "mechanism": "Readily crosses the blood-brain barrier and decarboxylates into serotonin (5-HT), which the pineal gland converts into natural endogenously timed melatonin.",
                    "evidence": "Controlled clinical trials demonstrate 5-HTP significantly reduces sleep onset latency while preserving natural REM cycles without pharmaceutical grogginess."
                },
                {
                    "name": "Low-Dose Micro-Melatonin (0.5mg - 1.5mg)",
                    "role": "Circadian Resynchronization",
                    "mechanism": "Calibrated specifically at conservative physiological levels to activate MT1 and MT2 receptors without desensitizing them or causing morning lethargy.",
                    "evidence": "Current chronobiology consensus confirms micro-doses (<1.5mg) are substantially more effective for long-term circadian timing than the obsolete 5mg–10mg megadoses found on pharmacy shelves."
                },
                {
                    "name": "L-Theanine (from Camellia sinensis)",
                    "role": "Alpha-Wave Neuromodulator",
                    "mechanism": "Stimulates 8–12 Hz alpha brain wave oscillations, inducing deep somatic relaxation and stress relief without artificial sedation or cognitive dulling.",
                    "evidence": "Electroencephalogram (EEG) human trials show measurable increases in alpha-frequency power within 30 minutes of oral administration."
                },
                {
                    "name": "Valerian Root Extract (Valeriana officinalis)",
                    "role": "Adenosine & GABA Receptor Synergist",
                    "mechanism": "Contains valerenic acid which inhibits the breakdown of endogenous GABA and modulates adenosine A1 receptors to prolong deep restorative sleep stages.",
                    "evidence": "A comprehensive 2023 meta-analysis encompassing 16 randomized controlled trials confirmed marked improvement in self-reported sleep quality among stress-induced insomnia cohorts."
                }
            ],
            "pricing_tiers": [
                {"supply": "2 Month Supply (2 Bottles)", "price": "$69 / bottle", "best_for": "First-Time Users & Mild Restlessness", "total": "$138", "savings": "Save $60"},
                {"supply": "3 Month Supply (3 Bottles)", "price": "$59 / bottle", "best_for": "Consistent Multi-Week Sleep Reset", "total": "$177", "savings": "Save $120 + 2 Free VIP Bonuses + Free US Shipping"},
                {"supply": "6 Month Supply (6 Bottles)", "price": "$49 / bottle", "best_for": "Best Overall Value & Long-Term Maintenance", "total": "$294", "savings": "Save $300 + 2 Free VIP Bonuses + Free Express Shipping"}
            ],
            "free_bonuses": [
                {"title": "Bonus #1: The 7-Day Circadian Reset Blueprint (VIP Digital Edition)", "desc": "Step-by-step master protocol detailing optimal morning photon exposure intervals, evening blue-light mitigation hacks, and thermal core-temperature timing to fall asleep in under 15 minutes."},
                {"title": "Bonus #2: The Restorative Deep Sleep Nutrition Handbook", "desc": "Clinically backed nutritional guide revealing the 5 hidden dinner foods that destroy slow-wave delta sleep, plus 3 nighttime herbal infusions that naturally potentiate GABA receptors."}
            ],
            "case_studies": [
                {"name": "Sandra M., 54", "location": "Phoenix, AZ", "scenario": "Chronic 3 AM awakenings and post-menopausal sleep disruption", "quote": "I have tried probably six different sleep supplements over the past three years and most left me with heavy morning brain fog. This formula was completely different from week one. I fall asleep within 15 minutes and no longer jolt awake in the middle of the night."},
                {"name": "James T., 41", "location": "Chicago, IL", "scenario": "Rotating night-shift ICU nurse with fragmented circadian schedule", "quote": "Rotating between day and night shifts wreaked havoc on my sleep architecture. Using this liquid protocol allowed me to achieve deep, uninterrupted daytime sleep even after demanding 12-hour trauma shifts. I feel restored rather than physically depleted."},
                {"name": "Rachel K., 37", "location": "Portland, OR", "scenario": "Tech executive tracking biometrics with an Oura Ring Gen 3", "quote": "I was skeptical about liquid delivery until I looked at my wearable sleep telemetry. Over 30 days, my Oura Ring recorded a verified 38% increase in restorative slow-wave deep sleep, while my sleep latency dropped from 42 minutes to under 12 minutes."}
            ],
            "safety_warnings": "Individuals taking prescription serotonergic agents (such as SSRIs, SNRIs, or tricyclic antidepressants) must consult a physician prior to using any formula containing 5-HTP. Avoid combining with alcohol, which suppresses REM sleep architecture. Not intended for individuals under 18 or those with untreated mechanical sleep apnea requiring CPAP intervention.",
            "counterfeit_notice": "Surging popularity has resulted in unauthorized third-party marketplace listings selling diluted, expired, or counterfeit batches lacking verified USP purity. Always purchase exclusively through the verified manufacturer link to ensure batch authenticity and activate the 60-day 100% money-back guarantee."
        }

    # 2. DENTAL & ORAL HEALTH (Prodentim, etc.)
    elif any(w in combined for w in ["dent", "teeth", "oral", "gum", "breath", "prodentim"]):
        return {
            "niche": "Oral Microbiome Ecology & Gum Tissue Defense",
            "format": "sublingual dissolvable probiotic micro-candies",
            "primary_benefit": "repopulation of beneficial oral bacteria, reduction of gum pocket inflammation, and natural enamel remineralization",
            "target_system": "oral cavity microbiome and sublingual saliva immunoglobulin-A defense",
            "regulatory": "FDA-registered, cGMP-audited facility in the United States using non-GMO, gluten-free certified active strains",
            "hook_analogy": "Treating chronic gum irritation and bad breath with harsh chemical mouthwashes is like bleaching your garden to kill weeds—it destroys your protective oral flora. Real long-term dental resilience requires repopulating your mouth with beneficial probiotic strains.",
            "ingredients": [
                {
                    "name": "Lactobacillus Paracasei",
                    "role": "Oral Mucosal Barrier & Sinus Cleansing",
                    "mechanism": "Inhibits periodontal pathogens, supports healthy gum epithelial attachment, and promotes free-flowing upper sinus cavities.",
                    "evidence": "Clinical trials demonstrate L. Paracasei significantly reduces salivary Streptococcus mutans counts while strengthening gingival tissue resilience."
                },
                {
                    "name": "B.lactis BL-04",
                    "role": "Immune Regulation & Microbiome Equilibrium",
                    "mechanism": "Competitively excludes pathogenic bacteria from tooth surfaces and supports mucosal immune defenses throughout the oral cavity.",
                    "evidence": "Published human studies confirm B.lactis BL-04 supports healthy respiratory and oral immunity while maintaining balanced oral pH."
                },
                {
                    "name": "Lactobacillus Reuteri",
                    "role": "Targeted Anti-Inflammatory Antimicrobial",
                    "mechanism": "Secretes reuterin, a natural broad-spectrum antimicrobial compound that targets periodontopathic bacteria and decreases gum bleeding indices.",
                    "evidence": "Multiple double-blind clinical trials indicate L. Reuteri supplementation significantly reduces plaque formation and gingival bleeding scores within 14 to 28 days."
                },
                {
                    "name": "Inulin (Chicory Root Oligosaccharide)",
                    "role": "Targeted Prebiotic Fiber",
                    "mechanism": "Acts as the specific nourishment fuel for beneficial oral strains while remaining non-fermentable by acid-producing cavity-causing microbes.",
                    "evidence": "Prebiotic research confirms inulin accelerates the colony-forming colonization of beneficial bifidobacteria and lactobacilli."
                },
                {
                    "name": "Malic Acid (from Pyrus malus)",
                    "role": "Natural Tooth Brightening & Salivary Flow",
                    "mechanism": "Stimulates natural saliva secretion to buffer oral acidity while gently lifting extrinsic tooth stains without abrasive enamel wear.",
                    "evidence": "Salivary stimulation is clinically proven as the body's primary biological defense mechanism against enamel demineralization."
                },
                {
                    "name": "Tricalcium Phosphate (TCP)",
                    "role": "Micro-Enamel Remineralization",
                    "mechanism": "Supplies bioavailable calcium and phosphate ions that integrate into microscopic enamel lesions to rebuild tooth density.",
                    "evidence": "In vitro and in vivo studies show functionalized TCP significantly enhances enamel surface micro-hardness."
                }
            ],
            "pricing_tiers": [
                {"supply": "1 Bottle (30-Day Supply)", "price": "$69 / bottle", "best_for": "Initial Trial & Fresh Breath Maintenance", "total": "$69", "savings": "Save $30"},
                {"supply": "3 Bottles (90-Day Supply)", "price": "$59 / bottle", "best_for": "Recommended Gum Pocket & Microbiome Reset", "total": "$177", "savings": "Save $120 + 2 Free VIP Bonuses + Free US Shipping"},
                {"supply": "6 Bottles (180-Day Supply)", "price": "$49 / bottle", "best_for": "Maximum Long-Term Protection & Wholesale Value", "total": "$294", "savings": "Save $300 + 2 Free VIP Bonuses + Free Express Shipping"}
            ],
            "free_bonuses": [
                {"title": "Bonus #1: Bad Breath Gone — One Day Rapid Detox Protocol", "desc": "A clinically designed handbook detailing 7 natural spice combinations and herbs that instantly neutralize sulfur-producing bacteria at the back of the tongue."},
                {"title": "Bonus #2: Hollywood White Teeth at Home Blueprint", "desc": "Reveals the simple 10-second brushing method and kitchen ingredients that lift stubborn coffee and tea stains without damaging delicate protective enamel."}
            ],
            "case_studies": [
                {"name": "Mark D., 49", "location": "Dallas, TX", "scenario": "Bleeding gums during flossing and chronic morning breath", "quote": "My dental hygienist was constantly warning me about deep 4mm and 5mm gum pockets. After three months of chewing these probiotic tablets, my dentist was stunned—my gum pockets reduced to healthy 2mm levels with zero bleeding during flossing."},
                {"name": "Elena R., 62", "location": "Tampa, FL", "scenario": "Enamel sensitivity and dry mouth complications", "quote": "Years of morning dry mouth made my teeth hypersensitive to cold water. This formula completely revitalized my natural saliva production. My teeth feel smooth like I just left a professional cleaning every single day."},
                {"name": "David W., 38", "location": "Seattle, WA", "scenario": "Chronic coffee drinker seeking natural dental whitening and freshness", "quote": "I drink three espressos a day and chemical mouthwashes always left a burning aftertaste that worsened my dry mouth. Switching to this probiotic completely eliminated coffee breath and my gums haven't felt this firm in ten years."}
            ],
            "safety_warnings": "Formulated with non-pathogenic probiotic strains generally recognized as safe (GRAS). If you are undergoing chemotherapy, take immunosuppressive medications, or have a central venous catheter, consult your dental physician prior to introducing high-potency probiotic cultures.",
            "counterfeit_notice": "Counterfeit imitation tablets containing inert sugar fillers have been reported on unauthorized third-party resale sites. Secure your order exclusively via the verified manufacturer link to ensure viable live bacterial strains and validate the 60-day money-back guarantee."
        }

    # 3. CARDIOVASCULAR & NITRIC OXIDE (Nitric Boost, etc.)
    elif any(w in combined for w in ["nitric", "blood", "cardio", "endurance", "pump", "vessel"]):
        return {
            "niche": "Vascular Endothelial Function & Nitric Oxide Synthesis",
            "format": "rapid-dissolve bioactive micronized powder / capsule",
            "primary_benefit": "enhanced arterial vasodilation, healthy systolic blood pressure support, and superior cellular stamina",
            "target_system": "endothelial nitric oxide synthase (eNOS) and vascular smooth muscle relaxation",
            "regulatory": "Manufactured in a certified cGMP facility in the USA, tested for heavy metal clearance and zero synthetic stims",
            "hook_analogy": "Relying on artificial caffeine stimulants for energy is like redlining an engine with dirty motor oil. Genuine sustained physical vigor comes from dilating blood vessels so oxygen and nutrients effortlessly reach working tissues.",
            "ingredients": [
                {
                    "name": "L-Citrulline Malate (2:1 Ratio)",
                    "role": "Endothelial Nitric Oxide Precursor",
                    "mechanism": "Bypasses splanchnic hepatic extraction, converting directly in the kidneys to systemic L-arginine to elevate plasma nitric oxide levels for up to 8 hours.",
                    "evidence": "Clinical trials show L-citrulline significantly increases flow-mediated dilation (FMD) and improves exercise capacity by up to 24% compared to standard L-arginine."
                },
                {
                    "name": "Standardized Beetroot Extract (Beta vulgaris)",
                    "role": "Inorganic Nitrate Reservoir",
                    "mechanism": "Utilizes the secondary nitrate-nitrite-NO enterosalivary pathway, delivering rapid vasodilation even under hypoxic or acidic physiological conditions.",
                    "evidence": "Sports medicine meta-analyses confirm dietary nitrates lower oxygen cost of submaximal exercise and support optimal cardiovascular efficiency."
                },
                {
                    "name": "French Maritime Pine Bark (Pycnogenol 95%)",
                    "role": "Endothelial eNOS Enzyme Activator",
                    "mechanism": "Contains potent oligomeric proanthocyanidins that stimulate the expression of endothelial nitric oxide synthase while neutralizing vascular superoxide radicals.",
                    "evidence": "Extensive double-blind human studies demonstrate Pycnogenol improves endothelial function and microcirculation in healthy adults."
                },
                {
                    "name": "Horny Goat Weed (Epimedium - Standardized Icariin)",
                    "role": "Natural cGMP Phosphodiesterase Modulator",
                    "mechanism": "Exerts targeted inhibitory action on PDE-5 enzymes, preventing the premature breakdown of cyclic GMP and sustaining vascular blood flow.",
                    "evidence": "Pharmacological research confirms icariin enhances penile and systemic arterial perfusion without the harsh side effects of prescription vasodilators."
                },
                {
                    "name": "Hawthorn Berry Extract (Crataegus oxyacantha)",
                    "role": "Myocardial Contractility & Blood Flow Support",
                    "mechanism": "Rich in bioflavonoids that relax peripheral vascular resistance, promote coronary arterial flow, and stabilize healthy blood pressure ranges.",
                    "evidence": "Cochrane Systematic Reviews validate hawthorn extract as an evidence-based adjunctive botanical for cardiovascular performance."
                },
                {
                    "name": "BioPerine Black Pepper Extract",
                    "role": "Thermonutrient Bioavailability Enhancer",
                    "mechanism": "Modulates intestinal epithelial cell kinetics, elevating systemic botanical absorption rates by up to 30%.",
                    "evidence": "Clinical pharmacokinetic trials verify piperine dramatically amplifies plasma co-ingredient bioavailability."
                }
            ],
            "pricing_tiers": [
                {"supply": "1 Bottle (30-Day Supply)", "price": "$69 / bottle", "best_for": "Initial Trial & Vascular Baseline Test", "total": "$69", "savings": "Save $30"},
                {"supply": "3 Bottles (90-Day Supply)", "price": "$59 / bottle", "best_for": "Endothelial Restoration & Stamina Protocol", "total": "$177", "savings": "Save $120 + 2 Free VIP Bonuses + Free US Shipping"},
                {"supply": "6 Bottles (180-Day Supply)", "price": "$49 / bottle", "best_for": "Best Overall Value & Continuous Cardiovascular Longevity", "total": "$294", "savings": "Save $300 + 2 Free VIP Bonuses + Free Express Shipping"}
            ],
            "free_bonuses": [
                {"title": "Bonus #1: The Nitric Oxide Nutritional Protocol (Digital Masterclass)", "desc": "Reveals the top 10 nitrate-dense whole foods and daily timing strategies that naturally double your circulation and physical stamina."},
                {"title": "Bonus #2: The Vascular Longevity & Blood Pressure Blueprint", "desc": "Practical daily manual explaining the simple 5-minute isometric breathing routine proven to support arterial flexibility and endothelial health."}
            ],
            "case_studies": [
                {"name": "Robert H., 58", "location": "Denver, CO", "scenario": "Sluggish afternoon fatigue and poor workout recovery", "quote": "At 58, my energy by 2 PM was nonexistent. Within three weeks of adding this formula to my morning routine, my stamina completely returned. My afternoon brain fog vanished and my workouts feel effortless."},
                {"name": "Carlos M., 45", "location": "Miami, FL", "scenario": "High-stress executive seeking vascular and circulatory optimization", "quote": "I wanted an alternative to chemical energy drinks that make your heart race. This formula gives you clean, calm, sustained physical stamina throughout the entire day. My daily vitality is back to my 30s."},
                {"name": "Greg S., 63", "location": "Atlanta, GA", "scenario": "Maintaining healthy blood pressure and active outdoor lifestyle", "quote": "My doctor wanted me focusing on cardiovascular conditioning. Taking this alongside my daily walking routine gave me a noticeable boost in endurance. I can hike 5 miles with my grandkids without feeling winded."}
            ],
            "safety_warnings": "Because this formula actively promotes vascular vasodilation, individuals taking prescription nitrates, blood pressure medications, or PDE-5 inhibitors must consult their cardiologist before use. Do not exceed the suggested serving size. Discontinue use 2 weeks prior to scheduled surgery.",
            "counterfeit_notice": "Avoid unauthorized marketplace listings that may contain unlisted synthetic fillers or expired batches. Orders placed through the official channel include batch purity verification and the comprehensive 60-day 100% money-back guarantee."
        }

    # 4. DEFAULT DYNAMIC RESEARCH ENGINE FOR ANY PRODUCT
    else:
        return {
            "niche": f"{category.replace('_', ' ').title()} & Performance Optimization",
            "format": "bioavailable clinically calibrated formula",
            "primary_benefit": f"targeted efficacy, validated purity standards, and measurable real-world outcomes for {topic}",
            "target_system": "cellular bioenergetics and functional physiological pathways",
            "regulatory": "Manufactured in a certified cGMP facility in the USA adhering to strict ISO and USP standards",
            "hook_analogy": "Investing in your well-being without verifying the underlying technical specifications is like buying a luxury vehicle without looking under the hood. Real performance is determined by component quality, not marketing hype.",
            "ingredients": [
                {
                    "name": "Core Bio-Active Complex A",
                    "role": "Primary Functional Driver",
                    "mechanism": f"Directly modulates cellular signaling pathways to support consistent physiological resilience and functional efficiency in {topic}.",
                    "evidence": "Peer-reviewed published literature validates marked improvements in functional markers compared to placebo."
                },
                {
                    "name": "Standardized Plant Botanical Matrix",
                    "role": "Secondary Synergistic Support",
                    "mechanism": "Provides high-potency bioflavonoids that protect active compounds from oxidative breakdown and accelerate cellular delivery.",
                    "evidence": "Randomized controlled trials confirm botanical synergy enhances active bioavailability by up to 28%."
                },
                {
                    "name": "Metabolic Cofactor Blend",
                    "role": "Cellular Bioenergetic Activation",
                    "mechanism": "Supplies essential mineral co-factors required for mitochondrial ATP generation and enzymatic reaction kinetics.",
                    "evidence": "Published clinical evaluations show significant reductions in daily physical and cognitive fatigue."
                },
                {
                    "name": "Phospholipid Delivery Vehicle",
                    "role": "Targeted Absorption Accelerator",
                    "mechanism": "Enhances intestinal membrane permeation, ensuring active ingredients survive digestion and reach systemic circulation intact.",
                    "evidence": "Comparative bioavailability trials demonstrate superior plasma retention curves."
                }
            ],
            "pricing_tiers": [
                {"supply": "Starter Package (1 Unit)", "price": "$69 / unit", "best_for": "Initial Evaluation & Short-Term Trial", "total": "$69", "savings": "Save $30"},
                {"supply": "Popular Bundle (3 Units)", "price": "$59 / unit", "best_for": "Recommended Multi-Month Optimization", "total": "$177", "savings": "Save $120 + 2 Free VIP Bonuses + Free Shipping"},
                {"supply": "Master Value Pack (6 Units)", "price": "$49 / unit", "best_for": "Maximum Long-Term Value & Savings", "total": "$294", "savings": "Save $300 + 2 Free VIP Bonuses + Priority Express Shipping"}
            ],
            "free_bonuses": [
                {"title": f"Bonus #1: The {topic} Quick-Start Protocol (VIP Digital Edition)", "desc": "Step-by-step master checklist revealing how to maximize results from Day 1 and optimize your daily routine."},
                {"title": "Bonus #2: The Ultimate Lifestyle Optimization Guide", "desc": "Practical daily manual covering nutritional synergy, timing hacks, and common mistakes to avoid for long-term success."}
            ],
            "case_studies": [
                {"name": "Michael S., 48", "location": "Austin, TX", "scenario": "Seeking dependable, verified daily results", "quote": f"I was skeptical after trying numerous over-hyped alternatives. {topic} delivered exactly what was promised within the first three weeks of consistent use."},
                {"name": "Karen L., 52", "location": "Charlotte, NC", "scenario": "Busy professional needing reliable long-term support", "quote": "The difference in quality and consistency is immediately noticeable. I appreciate the transparent formulation and the complete absence of unnecessary fillers."},
                {"name": "Thomas B., 41", "location": "Seattle, WA", "scenario": "Performance-focused consumer tracking measurable outcomes", "quote": f"I track my daily performance metrics diligently. Over a 30-day testing window, {topic} provided consistent improvements that far exceeded cheaper alternatives."}
            ],
            "safety_warnings": "Manufactured according to strict cGMP guidelines. If you are pregnant, nursing, taking prescription medications, or under medical supervision, consult your healthcare provider before introducing any new regimen.",
            "counterfeit_notice": "Protect yourself from expired or diluted counterfeit products sold through unauthorized third-party marketplaces. Order exclusively through the verified official link to secure batch authenticity and your 60-day satisfaction guarantee."
        }

def build_unique_article_content_for_angle(
    keyword: str,
    affiliate_url: str,
    topic: str,
    brand_name: str,
    angle_idx: int,
    category: str = "health_supplements",
    image_url_1: str = "",
    image_url_2: str = "",
    image_url_3: str = "",
    pasted_text: Optional[str] = None,
    scraped_data: Optional[Dict[str, Any]] = None,
    custom_title: str = "",
    secondary_keywords: str = "",
    theme_primary: str = "",
    theme_accent: str = ""
) -> Dict[str, Any]:
    raw_topic = (topic or keyword).strip()
    topic_clean = re.sub(r'[-–|:•]\s*(?:text\s*presentation|video\s*presentation|presentation|vsl|video\s*sales\s*letter|official\s*(?:website|site|store|page|portal)?|reviews?|store|shop|get|order|discount|buy\s*now|buy\s*online|supplement|formula|special\s*offer).*$', '', raw_topic, flags=re.IGNORECASE).strip()
    topic_clean = re.sub(r'\b(?:text|video)\s*presentation\b', '', topic_clean, flags=re.IGNORECASE).strip()
    topic_str = topic_clean if topic_clean else raw_topic
    brand_str = brand_name or "Verified Brand"
    topic_upper = topic_str.upper()

    res = get_product_deep_research(topic_str, keyword, brand_str, category)

    # Incorporate scraped data from affiliate sales page if available
    guarantee_days = 60
    if scraped_data and isinstance(scraped_data, dict):
        if scraped_data.get("guarantee_days"):
            guarantee_days = scraped_data["guarantee_days"]
        if scraped_data.get("format"):
            res["format"] = scraped_data["format"]
        if scraped_data.get("target_system"):
            res["target_system"] = scraped_data["target_system"]
        if scraped_data.get("pricing_tiers") and len(scraped_data["pricing_tiers"]) >= 2:
            res["pricing_tiers"] = scraped_data["pricing_tiers"]
        if scraped_data.get("bonuses") and len(scraped_data["bonuses"]) > 0:
            res["free_bonuses"] = scraped_data["bonuses"]

    # Resolve Theme Colors (Product Website Color Theme)
    resolved_primary = theme_primary.strip() if theme_primary and theme_primary.strip() else ""
    if not resolved_primary and scraped_data and isinstance(scraped_data, dict):
        resolved_primary = scraped_data.get("theme_primary", "")
    if not resolved_primary:
        resolved_primary = "#1e40af"  # Classic royal blue default

    resolved_accent = theme_accent.strip() if theme_accent and theme_accent.strip() else ""
    if not resolved_accent and scraped_data and isinstance(scraped_data, dict):
        resolved_accent = scraped_data.get("theme_accent", "")
    if not resolved_accent:
        resolved_accent = "#2563eb"

    theme_light_tint = hex_to_rgba(resolved_primary, 0.07)
    theme_border_tint = hex_to_rgba(resolved_primary, 0.22)

    angles = [
        {"id": "review", "name": "Clinical Review & Laboratory Formulation Analysis", "focus": "biochemistry & clinical evidence"},
        {"id": "buyer-guide", "name": "Official 2026 Buyer's Guide & Package Value", "focus": "package savings & bonuses"},
        {"id": "pros-cons", "name": "Honest Pros, Cons & Realistic Limitations", "focus": "limitations & contraindications"},
        {"id": "vs-alternatives", "name": "Head-to-Head Comparison vs Leading Market Alternatives", "focus": "competitor benchmarks"},
        {"id": "real-results", "name": "Verified Customer Results & 30-Day Biometric Tracker", "focus": "wearable data & shift routines"},
        {"id": "pricing-deals", "name": "Package Pricing, Volume Discounts & Free Bonuses", "focus": "cost-per-day & multi-pack tiers"},
        {"id": "safety-report", "name": "Clinical Safety Profile, Drug Interactions & Counterfeit Defense", "focus": "interactions & safety"},
        {"id": "formulation-deepdive", "name": "Active Ingredients & Pharmacokinetic Bioavailability", "focus": "delivery format & absorption"},
        {"id": "daily-protocol", "name": "30-Day Usage Protocol & Optimal Routine Blueprint", "focus": "timing & habit synergy"},
        {"id": "final-verdict", "name": "Comprehensive Category Scoring & Final Editorial Verdict", "focus": "final buying recommendation"}
    ]
    cur_angle = angles[angle_idx % len(angles)]

    titles = [
        f"{topic_str} Review: Ingredients, Evidence, Safety & Clinical Buying Guide",
        f"{topic_str} Complete Buyer's Guide: Packages, Pricing, Bonuses & Where to Buy",
        f"{topic_str} Honest Breakdown: 8 Standout Benefits, Real Flaws & Limitations",
        f"{topic_str} vs Leading Competitors: Head-to-Head Comparison & Benchmark Matrix",
        f"{topic_str} Real Results: 30-Day Timeline, Verified Case Studies & Wearable Data",
        f"Is {topic_str} Worth the Money? Package Breakdown, Real ROI & Buying Guide",
        f"{topic_str} Safety Report: Side Effects, Prescription Interactions & Purity Standards",
        f"{topic_str} Formulation Deep-Dive: 6 Active Ingredients & Absorption Science",
        f"Living with {topic_str}: Optimal 30-Day Daily Protocol & Routine Synergy",
        f"{topic_str} Final Verdict: Complete Scoring Matrix & Expert Purchasing Assessment"
    ]
    if custom_title and custom_title.strip():
        title = custom_title.strip()
    else:
        title = titles[angle_idx % len(titles)]

    meta_desc = f"Looking for the truth about {topic_str}? Read our independent {cur_angle['name']} covering verified ingredients, package pricing, real user results, and exclusive bonuses."

        # Smart Product Visual Resolution
    img1 = ""
    if scraped_data and isinstance(scraped_data, dict):
        if scraped_data.get("product_image_b64"):
            img1 = scraped_data["product_image_b64"]
        elif scraped_data.get("product_image"):
            img1 = scraped_data["product_image"]

    if not img1 and image_url_1 and image_url_1.strip():
        trimmed_u = image_url_1.strip()
        if os.path.exists(trimmed_u):
            try:
                with open(trimmed_u, "rb") as f_img:
                    ext = os.path.splitext(trimmed_u)[1].lstrip(".").lower() or "png"
                    b64_val = base64.b64encode(f_img.read()).decode("utf-8")
                    img1 = f"data:image/{ext};base64,{b64_val}"
            except Exception:
                img1 = trimmed_u
        else:
            img1 = trimmed_u

    if not img1:
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        yu_asset = os.path.join(curr_dir, "assets", "yu_sleep.png")
        if any(w in topic_str.lower() for w in ["yu sleep", "yusleep"]) and os.path.exists(yu_asset):
            try:
                with open(yu_asset, "rb") as f_img:
                    b64_val = base64.b64encode(f_img.read()).decode("utf-8")
                    img1 = f"data:image/png;base64,{b64_val}"
            except Exception:
                img1 = "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800"
        else:
            img1 = "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800" 

    # Distinct Intro Paragraphs per Angle
    if angle_idx == 0:
        intro_p1 = f"{topic_str} has become one of the most widely discussed formulations in the {res['niche']} category. {res['hook_analogy']} In this clinical review, our research team analyzes the active ingredients, the peer-reviewed literature, delivery format bioavailability, and real user feedback so you can make a fully informed purchasing decision."
        intro_p2 = f"The primary differentiator when investigating {topic_str} is the contrast between published trials on isolated compounds versus clinical synergy in a finished commercial blend. Manufactured in an {res['regulatory']}, this formula is designed to support {res['primary_benefit']} without synthetic stimulants or habit-forming dependencies."
    elif angle_idx == 1:
        intro_p1 = f"Before spending a dollar on {topic_str}, understanding the economic breakdown, package volume savings, and official distribution channels is essential. Many first-time buyers overpay by ordering single bottles or fall victim to unauthorized marketplace listings. This 2026 Buyer's Guide provides a clear decision framework for selecting the optimal supply package."
        intro_p2 = f"{topic_str} utilizes a {res['format']} engineered to target the body's {res['target_system']}. While single-month orders are available, clinical research consistently demonstrates that physiological adaptation takes several weeks. We examine the exact per-bottle savings, bundled digital bonuses, and verified guarantee terms."
    elif angle_idx == 2:
        intro_p1 = f"The wellness market is filled with promotional marketing promising overnight transformations. An authentic, responsible evaluation of {topic_str} requires an unfiltered look at what this {res['format']} can realistically achieve—and where its limitations lie. This honest breakdown cuts through the hype to highlight both standout strengths and critical trade-offs."
        intro_p2 = f"While {topic_str} is produced in an {res['regulatory']} and features evidence-backed compounds for {res['primary_benefit']}, it is not a magic cure-all. Individual biological response varies based on baseline health, dietary consistency, and concurrent medication use. Below, we examine who will benefit most and who should avoid this formula."
    elif angle_idx == 3:
        intro_p1 = f"Walk into any pharmacy or browse online health retailers, and you will encounter dozens of products making nearly identical claims for {res['niche']}. What separates {topic_str} from the noise is the specific multi-pathway architecture of its formula compared to generic single-ingredient alternatives. This comparative analysis benchmarks {topic_str} against mainstream competitors."
        intro_p2 = f"Most conventional drugstore brands rely heavily on blunt, high-dose single ingredients that research now suggests can cause receptor desensitization and grogginess. In contrast, {topic_str} employs a {res['format']} combining synergistic botanical extracts and amino acids to support {res['target_system']}. Here is our head-to-head scorecard."
    elif angle_idx == 4:
        intro_p1 = f"Laboratory mechanisms and manufacturer claims are foundational, but real-world verified customer outcomes provide the ultimate proof of efficacy. In this report, we examine customer feedback collected from verified purchasers, including shift workers, older adults, and individuals tracking objective biometric data via wearable technology."
        intro_p2 = f"Unlike anecdotal testimonials that lack verifiable context, tracking biological adaptation across a 30-day timeline reveals a clear progression: rapid acute calm during Week 1, followed by deeper cellular stabilization between Weeks 3 and 6. Below are real-world case studies demonstrating how {topic_str} performs under everyday conditions."
    elif angle_idx == 5:
        intro_p1 = f"Evaluating the financial value of a premium health investment requires looking beyond the sticker price. In this value breakdown for {topic_str}, we calculate the exact cost-per-day across all authorized multi-bottle supply tiers, analyze bundled VIP bonuses, and verify the risk-free return terms."
        intro_p2 = f"Many consumers make the mistake of ordering single units month-to-month, incurring unnecessary shipping costs while missing out on volume discounts. We break down why the 3-month and 6-month packages represent the highest return on investment for biological adaptation."
    elif angle_idx == 6:
        intro_p1 = f"Safety and purity standards must always take precedence when choosing an ingestible wellness product. This clinical safety audit investigates the compounding protocols, allergen disclosures, prescription drug interactions, and manufacturing certifications behind {topic_str}."
        intro_p2 = f"Because {topic_str} actively influences {res['target_system']}, understanding potential contraindications with pharmaceutical medications is vital. We also provide an urgent advisory regarding unauthorized third-party marketplace listings."
    elif angle_idx == 7:
        intro_p1 = f"The true effectiveness of any supplement comes down to its biochemical formulation and delivery kinetics. This technical deep-dive examines the molecular mechanisms, bioavailability advantages, and synergistic ratios that define {topic_str}."
        intro_p2 = f"Traditional tablets and capsules suffer from extensive hepatic first-pass degradation. By contrast, the {res['format']} utilized in {topic_str} preserves active compound integrity for superior systemic absorption. Here is the science behind each active constituent."
    elif angle_idx == 8:
        intro_p1 = f"Maximizing the benefits of {topic_str} requires integrating it into a consistent, supportive daily protocol. This practical implementation guide outlines optimal dosing timing, dietary pairings, and evening routines to amplify your results from Day 1 through Day 30."
        intro_p2 = f"Supplements work best in synergy with natural physiology. By aligning your {topic_str} intake with circadian cues and lifestyle habits, you establish the foundation for lasting wellness and cellular recovery."
    else:
        intro_p1 = f"After conducting a comprehensive evaluation of the clinical literature, manufacturing standards, package economics, and verified customer experiences, our editorial board presents the final assessment of {topic_str}."
        intro_p2 = f"In a marketplace crowded with commoditized alternatives, {topic_str} establishes category leadership through clean labeling, evidence-backed ingredient dosing, and verifiable consumer satisfaction. Below is our final scoring breakdown and recommendation."

    # Section 1: What is {topic}
    what_is_text = f"<strong>{topic_str}</strong> is a specialized {res['format']} developed to address {res['primary_benefit']}. Unlike conventional capsule-based products that often absorb erratically depending on gut microbiome health and digestive transit time, this formulation is engineered for superior cellular bioavailability.<br><br>The formula targets what researchers term the body's <em>{res['target_system']}</em>, supporting natural biological equilibrium rather than overriding bodily systems with forced sedation or aggressive stimulation. Every batch is compounded in an {res['regulatory']} ensuring strict verification of active compound potency, absence of heavy metal contaminants, and verified label accuracy."

    # Section 2: Ingredients Breakdown HTML (6 Detailed Ingredients!)
    ing_cards = []
    for ing in res["ingredients"]:
        ing_cards.append(f"""
        <div style="background: #ffffff; border: 1.5px solid #cbd5e1; border-left: 4.5px solid #2563eb; border-radius: 6px; padding: 12px 16px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <strong style="color: #1e3a8a; font-size: 10.5pt;">{ing['name']}</strong>
                <span style="background: #dbeafe; color: #1e40af; font-size: 7.5pt; font-weight: 700; padding: 2px 8px; border-radius: 4px;">{ing['role']}</span>
            </div>
            <p style="margin: 0 0 6px 0; font-size: 9.2pt; color: #334155; line-height: 1.45;">{ing['mechanism']}</p>
            <div style="background: #f8fafc; border-radius: 4px; padding: 6px 10px; font-size: 8.5pt; color: #475569; font-style: italic;">
                <strong>🔬 Clinical Evidence:</strong> {ing['evidence']}
            </div>
        </div>
        """)
    sec2_heading = f"Key Active Ingredients & Scientific Mode of Action in {topic_str}"
    sec2_text = f"What separates an effective formula from generic market hype is the quality, dosing, and clinical justification of its active compounds. Below is the verified breakdown of the key ingredients in <strong>{topic_str}</strong>:" + "".join(ing_cards)

    # Section 3: Real User Case Studies (Sandra, James, Rachel & Biometrics)
    case_cards = []
    for cs in res["case_studies"]:
        case_cards.append(f"""
        <div style="background: #ffffff; border: 1px solid #cbd5e1; border-left: 4px solid #16a34a; border-radius: 6px; padding: 12px 14px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <strong style="color: #0f172a; font-size: 9.5pt;">{cs['name']} — {cs['location']}</strong>
                <span style="font-size: 8pt; color: #166534; font-weight: 700;">Verified Purchaser ✅</span>
            </div>
            <div style="font-size: 8.5pt; color: #64748b; margin-bottom: 6px; font-style: italic;">Profile: {cs['scenario']}</div>
            <p style="margin: 0; font-size: 9pt; color: #334155; line-height: 1.4;">"{cs['quote']}"</p>
        </div>
        """)
    benefits_limits_text = f"Real-world user experiences across diverse age groups and lifestyles confirm consistent outcomes when {topic_str} is taken regularly. Below are verified case reports from ongoing 2026 consumer audits:" + "".join(case_cards)

    # Section 4: Safety, Side Effects, Drug Interactions & Counterfeit Warnings
    safety_standards_text = f"""
    <strong>Safety Profile & Known Sensitivities:</strong><br>
    The active ingredients in <strong>{topic_str}</strong> possess well-characterized safety profiles supported by extensive dietary use and clinical evaluation. The formulation contains zero synthetic hormones, habit-forming sedatives, or harsh pharmaceutical compounds. Mild, transient adjustments may occur during the first 3–5 days as natural physiological balance is restored.<br><br>
    <strong>⚠️ Important Prescription Drug Interactions & Contraindications:</strong><br>
    {res['safety_warnings']}<br><br>
    <div style="background: #fff1f2; border: 1.5px solid #fecdd3; border-left: 4.5px solid #e11d48; border-radius: 6px; padding: 10px 14px; margin-top: 10px;">
        <strong style="color: #9f1239; font-size: 9.5pt;">⚠️ Official Anti-Counterfeit Advisory:</strong><br>
        <span style="font-size: 8.8pt; color: #881337;">{res['counterfeit_notice']}</span>
    </div>
    """

    # Section 5: Pricing Packages Table + 2 Free VIP Bonuses Box
    price_rows = "".join([f"""
    <tr>
        <td style="padding: 9px 12px; font-weight: 700; color: #0f172a;">{pt.get('supply', 'Package')}</td>
        <td style="padding: 9px 12px; font-weight: 800; color: {resolved_primary};">{pt.get('price', '$69 / bottle')}</td>
        <td style="padding: 9px 12px; color: #334155;">{pt.get('best_for', 'Verified Direct Official Supply')}</td>
        <td style="padding: 9px 12px; color: #16a34a; font-weight: 700;">{pt.get('savings', 'Special Discount')}</td>
    </tr>
    """ for pt in res["pricing_tiers"]])

    bonus_box_list = []
    for b in res["free_bonuses"]:
        b_img = b.get("image_b64") or b.get("image") or ""
        b_val = b.get("value", "$59.00")
        if b_img:
            bonus_box_list.append(f"""
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; display: flex; align-items: center; gap: 14px;">
                <div style="flex-shrink: 0; width: 85px; text-align: center;">
                    <img src="{b_img}" alt="{b['title']}" style="max-width: 85px; max-height: 105px; object-fit: contain; border-radius: 4px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); background: #ffffff;">
                </div>
                <div style="flex-grow: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <strong style="color: #166534; font-size: 9.8pt;">🎁 {b['title']}</strong>
                        <span style="background: #dcfce7; color: #15803d; font-size: 8pt; font-weight: 800; padding: 2px 8px; border-radius: 4px;">Value: {b_val} (FREE)</span>
                    </div>
                    <p style="margin: 0; font-size: 8.8pt; color: #14532d; line-height: 1.45;">{b['desc']}</p>
                </div>
            </div>
            """)
        else:
            bonus_box_list.append(f"""
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 10px 12px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">
                    <strong style="color: #166534; font-size: 9.5pt;">🎁 {b['title']}</strong>
                    <span style="background: #dcfce7; color: #15803d; font-size: 7.8pt; font-weight: 800; padding: 2px 6px; border-radius: 4px;">Free Value: {b_val}</span>
                </div>
                <p style="margin: 3px 0 0 0; font-size: 8.8pt; color: #14532d; line-height: 1.4;">{b['desc']}</p>
            </div>
            """)
    bonus_boxes = "".join(bonus_box_list)

    price_value_text = f"""
    <strong>Official 2026 Package Tiers & Volume Savings:</strong><br>
    To encourage consistent multi-week supplementation—which is essential for biological adaptation—the manufacturer provides substantial volume discounts on multi-bottle packages. Below is the current authorized pricing schedule:
    <div style="margin: 12px 0 16px 0; overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 8.8pt; text-align: left; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;">
            <thead>
                <tr style="background: #1e3a8a; color: #ffffff;">
                    <th style="padding: 10px 12px;">Package Supply</th>
                    <th style="padding: 10px 12px;">Price Per Bottle</th>
                    <th style="padding: 10px 12px;">Recommended Best For</th>
                    <th style="padding: 10px 12px;">Total Savings</th>
                </tr>
            </thead>
            <tbody>
                {price_rows}
            </tbody>
        </table>
    </div>
    <div style="background: #fffbeb; border: 1.5px solid #fde68a; border-radius: 8px; padding: 14px 16px; margin: 14px 0;">
        <h4 style="margin: 0 0 10px 0; color: #92400e; font-size: 11pt;">🎁 Exclusive Free Digital Bonuses Included with 3 & 6 Bottle Orders:</h4>
        {bonus_boxes}
        <p style="margin: 8px 0 12px 0; font-size: 8.5pt; color: #78350f; font-weight: 600;">
            ✔ Instant Digital Download After Checkout • 100% Risk-Free {guarantee_days}-Day Money-Back Guarantee
        </p>
        <div style="text-align: center; margin-top: 14px;">
            <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="rc-btn rc-btn-coral" style="padding: 12px 34px; font-size: 10.5pt; display: inline-block;">
                CLAIM 6-BOTTLE DISCOUNT{' + ' + str(len(res['free_bonuses'])) + ' FREE BONUSES' if len(res.get('free_bonuses', [])) > 0 else ''} NOW
            </a>
            <div class="rc-trust-subline">Official Site • Free Express Shipping • {guarantee_days}-Day Guarantee</div>
        </div>
    </div>
    """

    # Comparison Table HTML
    table_html = f"""
    <div style="margin: 14px 0; overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 8.8pt; text-align: left; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;">
            <thead>
                <tr style="background: #1e3a8a; color: #ffffff;">
                    <th style="padding: 10px 12px; width: 25%;">Comparison Criteria</th>
                    <th style="padding: 10px 12px; width: 38%; background: #2563eb;">{topic_str} (Nano-Enhanced)</th>
                    <th style="padding: 10px 12px; width: 37%;">Generic Pharmacy / OTC Brands</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 9px 12px; font-weight: 700;">Delivery & Absorption</td>
                    <td style="padding: 9px 12px; color: #16a34a; font-weight: 700;">Sublingual {res['format']} (Rapid Direct Uptake)</td>
                    <td style="padding: 9px 12px; color: #dc2626;">Standard capsules/tablets (Gut degradation)</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0; background: #f8fafc;">
                    <td style="padding: 9px 12px; font-weight: 700;">Formulation Scope</td>
                    <td style="padding: 9px 12px; color: #16a34a; font-weight: 700;">Multi-Pathway Synergistic Complex (6+ Actives)</td>
                    <td style="padding: 9px 12px; color: #dc2626;">Single isolated compound (Blunt single-pathway)</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 9px 12px; font-weight: 700;">Safety & Tolerance</td>
                    <td style="padding: 9px 12px; color: #16a34a; font-weight: 700;">Non-habit forming, no morning grogginess</td>
                    <td style="padding: 9px 12px; color: #dc2626;">High-dose grogginess & receptor desensitization</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0; background: #f8fafc;">
                    <td style="padding: 9px 12px; font-weight: 700;">Manufacturing Standard</td>
                    <td style="padding: 9px 12px; color: #16a34a; font-weight: 700;">FDA-registered, cGMP-certified USA facility</td>
                    <td style="padding: 9px 12px; color: #64748b;">Varying standards, often imported bulk powder</td>
                </tr>
                <tr>
                    <td style="padding: 9px 12px; font-weight: 700;">Guarantee & Bonuses</td>
                    <td style="padding: 9px 12px; color: #16a34a; font-weight: 700;">{res.get('guarantee_days', 60)}-Day 100% Refund + {len(res.get('free_bonuses', []))} Free VIP Digital Guides</td>
                    <td style="padding: 9px 12px; color: #64748b;">No money-back guarantee once opened</td>
                </tr>
            </tbody>
        </table>
    </div>
    """

    num_b = len(res.get('free_bonuses', []))
    bonus_phrase = f"{num_b} exclusive VIP digital bonuses" if num_b > 1 else "exclusive VIP digital bonuses"

    pros_points = [
        f"Multi-pathway formula addressing {res['target_system']} simultaneously",
        f"Advanced {res['format']} ensures superior bioavailability over swallowed capsules",
        f"Contains zero synthetic sedatives, harsh stimulants, or habit-forming substances",
        f"Compounded exclusively in an {res['regulatory']}",
        f"Multi-bottle supply tiers provide up to 50% wholesale savings",
        f"Includes {bonus_phrase} and free shipping on popular packages",
        f"Backed by an unconditional {res.get('guarantee_days', 60)}-day 100% money-back satisfaction guarantee",
        f"Supported by peer-reviewed published clinical trials in reputable medical journals"
    ]
    cons_points = [
        f"Only available for purchase through the official manufacturer website",
        f"Premium price point reflecting specialized compounding and certified testing",
        f"Requires daily consistency for 3 to 6 weeks to achieve full biological adaptation",
        f"High demand occasionally results in temporary stock shortages",
        f"Not intended for pregnant or nursing individuals without prior medical clearance"
    ]

    checklist_points = [
        f"Order exclusively through the official channel to guarantee genuine USP-grade batch purity",
        f"Choose the 3-month or 6-month package to secure maximum savings and all {num_b} free digital bonuses",
        f"Review the full active ingredient panel with your physician if taking prescription medications",
        f"Commit to a minimum 30-day consistent daily protocol to allow full cellular adaptation",
        f"Save your digital order confirmation to activate your {res.get('guarantee_days', 60)}-day 100% money-back guarantee"
    ]

    faqs = [
        (f"How does {topic_str} differ from standard over-the-counter alternatives?", f"{topic_str} utilizes a {res['format']} designed for rapid cellular absorption. Unlike single-ingredient drugstore products that rely on blunt megadoses, {topic_str} targets {res['target_system']} with synergistic botanical extracts and amino acids."),
        (f"How long does it take to experience noticeable results with {topic_str}?", f"Most users report initial improvements within the first 7 to 10 days of consistent use. The most profound biological adaptations occur between weeks 3 and 6 as cellular reserves stabilize."),
        (f"Is {topic_str} habit-forming or dependency-inducing?", f"No. The formula contains zero synthetic sedatives or scheduled compounds. It works by supporting your natural physiology rather than forcing artificial sedation."),
        (f"What is the recommended daily dosage protocol?", f"Follow the manufacturer label printed on the bottle precisely. Consistency at the same time each day is far more effective than taking sporadic double doses."),
        (f"Can older adults use {topic_str} safely?", f"Yes. Older adults experiencing natural age-related biological declines often benefit significantly. If taking prescription medications, consult your physician."),
        (f"Does {topic_str} cause next-day grogginess or brain fog?", f"No. The low-dose, synergistic formulation is specifically calibrated to avoid morning lethargy or cognitive impairment."),
        (f"Can I take {topic_str} alongside other dietary supplements?", f"Generally yes. However, avoid stacking with products containing overlapping active ingredients or serotonergic compounds."),
        (f"What if {topic_str} does not work for my biology?", f"Every order through the official portal is backed by an unconditional 60-day 100% money-back guarantee."),
        (f"Are there any artificial fillers or common allergens in the formula?", f"The product is compounded without gluten, soy, dairy, or synthetic colorings in an FDA-registered facility."),
        (f"Where is the safest place to order authentic {topic_str}?", f"Order exclusively through the official verified website linked in this report to avoid counterfeit or expired batches.")
    ]

    final_verdict_text = f"""
    Following an exhaustive review of the clinical formulation, pharmacokinetic delivery science, manufacturing audits, and verified customer experiences, <strong>{topic_str}</strong> stands out as a genuine category leader in the {res['niche']} space.<br><br>
    Its multi-pathway botanical synergy, superior {res['format']}, and strict cGMP production standards position it well ahead of commoditized drugstore alternatives. For consumers seeking a dependable, non-habit-forming solution to support <strong>{res['primary_benefit']}</strong>, {topic_str} earns our highest editorial recommendation.<br><br>
    The <strong>6-Month Supply ($49/bottle)</strong> delivers the greatest overall value and provides adequate time for complete biological adaptation, while the <strong>3-Month Supply ($59/bottle)</strong> is an excellent starting point for new users. Both bundles include 2 free VIP digital bonuses and free shipping under the 60-day money-back guarantee.
    """

    # Merge Primary & Secondary Keywords into Search Keywords Index & Google Metadata
    sec_kws = [k.strip() for k in secondary_keywords.split(",") if k.strip()] if secondary_keywords else []
    base_kw_list = generate_unique_keywords_for_angle(keyword, topic_str, "technical_review")
    
    combined_kws = []
    seen = set()
    for kw_cand in sec_kws + [keyword] + base_kw_list:
        kw_clean = kw_cand.strip()
        if kw_clean and kw_clean.lower() not in seen:
            seen.add(kw_clean.lower())
            combined_kws.append(kw_clean)
            
    keywords_list = combined_kws[:30]
    keywords_html = "".join([f"<li>• {kw}</li>\n" for kw in keywords_list])

    toc_items = [
        ("what-is", f"1. What is {topic_str}? Understanding This {keyword}"),
        ("architecture", f"2. Key Active Ingredients & Clinical Mode of Action"),
        ("benefits-limits", f"3. Verified Customer Results & Biometric Case Studies"),
        ("safety-standards", f"4. Safety Profile, Drug Interactions & Counterfeit Warnings"),
        ("price-value", f"5. Package Pricing Tiers, Volume Savings & Free Bonuses"),
        ("comparison", f"6. How {topic_str} Compares with Leading Alternatives"),
        ("pros-cons", f"7. Pros and Cons: Standout Advantages & Limitations"),
        ("checklist", f"8. A Practical Buying Checklist for {topic_str}"),
        ("faqs", f"9. Frequently Asked Questions: {topic_str} {keyword}"),
        ("verdict", f"10. Final Assessment: Is {topic_str} Worth Buying?")
    ]
    toc_html = "".join([f'<li><a href="#{slug}">{title_text}</a></li>\n' for slug, title_text in toc_items])

    pros_html = "".join([f"<li>• {p}</li>\n" for p in pros_points])
    cons_html = "".join([f"<li>• {c}</li>\n" for c in cons_points])
    checklist_html = "".join([f"<li><span class='check-mark'>✓</span> {item}</li>\n" for item in checklist_points])

    faqs_html = ""
    for q_text, a_text in faqs:
        faqs_html += f"""
        <div class="faq-item">
            <h4>{q_text}</h4>
            <p>{a_text}</p>
        </div>
        """

    # Executive Product Fact Sheet & Specs Card (With Official Product Showcase Thumbnail & Brand Theme)
    exec_summary_html = f"""
    <div style="background: #ffffff; border: 1.5px solid #cbd5e1; border-top: 4px solid {resolved_primary}; border-radius: 8px; padding: 14px 18px; margin: 16px 0; box-shadow: 0 3px 10px rgba(0,0,0,0.04);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">
            <div>
                <span style="font-size: 7.5pt; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 800; color: {resolved_primary}; background: {theme_light_tint}; padding: 2px 8px; border-radius: 4px;">Executive Fact Sheet</span>
                <h3 style="margin: 4px 0 0 0; font-size: 13pt; color: #0f172a; font-weight: 800;">{topic_str} Specification Summary</h3>
            </div>
            <div style="text-align: right;">
                <div style="color: #f59e0b; font-size: 11pt; font-weight: 800;">★★★★★ 4.9 / 5.0</div>
                <div style="font-size: 7.5pt; color: #64748b;">(3,800+ Verified User Audits)</div>
            </div>
        </div>
        
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 8px;">
            <tr>
                <td style="width: 28%; vertical-align: middle; text-align: center; padding-right: 14px; border-right: 1px solid #f1f5f9;">
                    <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener">
                        <img src="{img1}" alt="{topic_str}" style="max-width: 100%; max-height: 155px; object-fit: contain; display: block; margin: 0 auto; border-radius: 6px;" onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=600';">
                    </a>
                    <div style="font-size: 7.5pt; color: #15803d; font-weight: 800; margin-top: 6px; text-transform: uppercase; letter-spacing: 0.3px;">✔ Official Product</div>
                    <div style="font-size: 7pt; color: #64748b;">Batch Authenticity Verified</div>
                </td>
                <td style="width: 72%; vertical-align: top; padding-left: 14px;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 8.8pt;">
                        <tr>
                            <td style="padding: 4px 6px; color: #475569; font-weight: 600; width: 34%; border-bottom: 1px solid #f1f5f9;">Product Category:</td>
                            <td style="padding: 4px 6px; color: #0f172a; font-weight: 700; border-bottom: 1px solid #f1f5f9;">{res['niche']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 6px; color: #475569; font-weight: 600; border-bottom: 1px solid #f1f5f9;">Delivery Format:</td>
                            <td style="padding: 4px 6px; color: #0f172a; font-weight: 700; border-bottom: 1px solid #f1f5f9;">{res['format'].title()}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 6px; color: #475569; font-weight: 600; border-bottom: 1px solid #f1f5f9;">Biological Target:</td>
                            <td style="padding: 4px 6px; color: #0f172a; font-weight: 700; border-bottom: 1px solid #f1f5f9;">{res['target_system'].title()}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 6px; color: #475569; font-weight: 600; border-bottom: 1px solid #f1f5f9;">Manufacturing Standards:</td>
                            <td style="padding: 4px 6px; color: #0f172a; font-weight: 700; border-bottom: 1px solid #f1f5f9;">FDA-Registered & cGMP Certified USA Facility</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 6px; color: #475569; font-weight: 600; border-bottom: 1px solid #f1f5f9;">Purity Verification:</td>
                            <td style="padding: 4px 6px; color: #0f172a; font-weight: 700; border-bottom: 1px solid #f1f5f9;">Third-Party Tested, Non-GMO, Stimulant-Free</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 6px; color: #475569; font-weight: 600;">Guarantee Protection:</td>
                            <td style="padding: 4px 6px; color: #16a34a; font-weight: 800;">{guarantee_days}-Day 100% Unconditional Money-Back Guarantee</td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        
        <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px; padding: 5px 10px; text-align: center;">
            <span style="color: #15803d; font-size: 8.2pt; font-weight: 700;">✔ Verified Authentic Batch • Direct-from-Manufacturer Official Distribution Link</span>
        </div>
    </div>
    """

    return {
        "exec_summary_html": exec_summary_html,
        "guarantee_days": guarantee_days,
        "theme_primary": resolved_primary,
        "theme_accent": resolved_accent,
        "theme_light_tint": theme_light_tint,
        "theme_border_tint": theme_border_tint,
        "title": title,
        "meta_desc": meta_desc,
        "keyword": keyword,
        "topic": topic_str,
        "topic_upper": topic_upper,
        "brand": brand_str,
        "affiliate_url": affiliate_url,
        "img1": img1,
        "intro_p1": intro_p1,
        "intro_p2": intro_p2,
        "what_is_text": what_is_text,
        "sec2_heading": sec2_heading,
        "sec2_text": sec2_text,
        "benefits_limits_text": benefits_limits_text,
        "safety_standards_text": safety_standards_text,
        "price_value_text": price_value_text,
        "pros_html": pros_html,
        "cons_html": cons_html,
        "checklist_html": checklist_html,
        "table_html": table_html,
        "toc_html": toc_html,
        "faqs_html": faqs_html,
        "keywords_list": keywords_list,
        "keywords_html": keywords_html,
        "final_verdict_text": final_verdict_text
    }

def generate_master_pdf_html(data: Dict[str, Any], button_color: str = "#08796f") -> str:
    """
    Renders the exact Joint Genesis authority layout:
    - Forest Teal (#143a35 / #08796f) headings & soft mint (#e6f4f1) comparison table.
    - Running footer on every page: '{TOPIC} | INDEPENDENT BUYING GUIDE' + Page counter.
    - Page 1: Title, Meta Description, rich opening, centered primary CTA pill button.
    - Page 2: Centered product visual with publisher caption + clean 'In this guide' Table of Contents.
    - Pages 3-8: In-depth analysis, secondary pill CTA buttons, comparison table, pros & cons, checklist, 10 FAQs, and final assessment.
    - Pages 9-10: 'Search Keywords' page with disclaimer note and 20-25 bulleted keywords.
    - ZERO affiliate disclosure throughout.
    """
    title = data["title"]
    meta_desc = data["meta_desc"]
    affiliate_url = data["affiliate_url"]
    topic = data["topic"]
    topic_upper = data["topic_upper"]
    keyword = data["keyword"]
    img1 = data["img1"]
    theme_primary = data.get("theme_primary") or "#143a35"
    theme_accent = data.get("theme_accent") or button_color or "#08796f"
    theme_light_tint = data.get("theme_light_tint") or "#e6f4f1"
    theme_border_tint = data.get("theme_border_tint") or "#d7e8e4"
    resolved_btn_color = button_color if button_color not in ["#08796f", "#2563eb"] else theme_accent

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <meta name="description" content="{meta_desc}">
    <style>
        @page {{
            size: A4 portrait;
            margin: 18mm 18mm 20mm 18mm;
            @bottom-left {{
                content: "{topic_upper}  |  INDEPENDENT BUYING GUIDE";
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 8pt;
                color: #697c77;
                border-top: 1px solid {theme_border_tint};
                padding-top: 6px;
            }}
            @bottom-right {{
                content: counter(page);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 8pt;
                color: #697c77;
                border-top: 1px solid {theme_border_tint};
                padding-top: 6px;
            }}
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #222928;
            background: #ffffff;
            line-height: 1.62;
            font-size: 10pt;
        }}

        /* PAGE BREAK UTILITIES */
        .page-break-after {{
            page-break-after: always;
            break-after: page;
        }}
        .page-break-before {{
            page-break-before: always;
            break-before: page;
        }}
        .no-break {{
            page-break-inside: avoid;
            break-inside: avoid;
        }}

        /* TYPOGRAPHY */
        h1.article-title {{
            font-size: 22pt;
            font-weight: 800;
            color: {theme_primary};
            line-height: 1.25;
            margin-bottom: 12px;
            letter-spacing: -0.3px;
        }}

        p.meta-description {{
            font-size: 10.5pt;
            color: #53615e;
            line-height: 1.55;
            margin-bottom: 20px;
        }}

        h2.sec-heading {{
            font-size: 14pt;
            font-weight: 700;
            color: {theme_primary};
            margin-top: 22px;
            margin-bottom: 8px;
            line-height: 1.35;
            page-break-after: avoid;
            break-after: avoid;
        }}

        h3.sub-sec-heading {{
            font-size: 11pt;
            font-weight: 700;
            color: {theme_accent};
            margin-top: 14px;
            margin-bottom: 6px;
            page-break-after: avoid;
            break-after: avoid;
        }}

        p {{
            margin-bottom: 12px;
            text-align: justify;
            color: #222928;
            font-size: 10pt;
        }}

        strong {{
            color: {theme_primary};
            font-weight: 700;
        }}

        /* CTA BUTTONS */
        .cta-container {{
            text-align: center;
            margin: 18px 0 22px 0;
            page-break-inside: avoid;
            break-inside: avoid;
        }}

        .cta-pill-btn {{
            display: inline-block;
            background-color: {resolved_btn_color};
            color: #ffffff !important;
            font-size: 10.5pt;
            font-weight: 700;
            text-decoration: none !important;
            padding: 11px 32px;
            border-radius: 24px;
            letter-spacing: 0.2px;
            border: none;
            box-shadow: 0 3px 8px rgba(0, 0, 0, 0.2);
        }}

        .cta-secondary-btn {{
            display: inline-block;
            background-color: {resolved_btn_color};
            color: #ffffff !important;
            font-size: 9.5pt;
            font-weight: 700;
            text-decoration: none !important;
            padding: 8px 24px;
            border-radius: 20px;
            border: none;
        }}

        /* PAGE 2: PRODUCT VISUAL & TOC */
        .product-visual-wrapper {{
            text-align: center;
            margin-top: 10px;
            margin-bottom: 20px;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .product-visual-img {{
            max-width: 280px;
            max-height: 280px;
            object-fit: contain;
            border-radius: 6px;
            border: 1px solid {theme_border_tint};
            background: #ffffff;
            padding: 10px;
        }}
        .visual-caption {{
            font-size: 8.5pt;
            color: #64748b;
            margin-top: 8px;
            font-style: italic;
            text-align: center;
            line-height: 1.4;
        }}

        .toc-container {{
            margin-top: 18px;
            padding: 14px 18px;
            border-top: 1px solid {theme_border_tint};
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .toc-title {{
            font-size: 15pt;
            font-weight: 800;
            color: {theme_primary};
            margin-bottom: 12px;
        }}
        .toc-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .toc-list li {{
            margin-bottom: 8px;
            font-size: 10pt;
        }}
        .toc-list a {{
            color: {theme_primary};
            text-decoration: none;
            font-weight: 500;
        }}
        .toc-list a:hover {{
            text-decoration: underline;
        }}

        /* COMPARISON TABLE */
        .table-container {{
            margin: 16px 0;
        }}
        table.comparison-table tr {{
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        table.comparison-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 8.8pt;
        }}
        table.comparison-table th, table.comparison-table td {{
            padding: 10px 12px;
            border: 1px solid #cbd5e1;
            text-align: left;
            vertical-align: top;
        }}
        table.comparison-table th {{
            background: {theme_light_tint};
            color: {theme_primary};
            font-weight: 700;
            font-size: 9pt;
        }}
        table.comparison-table tr:nth-child(even) {{
            background: #fbfdfc;
        }}

        /* PROS & CONS */
        .pros-cons-section {{
            margin: 16px 0;
        }}
        ul.plain-bullets {{
            list-style: none;
            padding: 0;
            margin-bottom: 14px;
        }}
        ul.plain-bullets li {{
            font-size: 9.5pt;
            color: #222928;
            margin-bottom: 6px;
            line-height: 1.45;
        }}

        /* CHECKLIST */
        .checklist-box {{
            background: #fbfdfc;
            border: 1px solid #d7e8e4;
            border-radius: 6px;
            padding: 14px 18px;
            margin: 16px 0;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        ul.checklist {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        ul.checklist li {{
            font-size: 9.5pt;
            color: #222928;
            margin-bottom: 8px;
            line-height: 1.45;
            display: flex;
            align-items: flex-start;
            gap: 8px;
        }}
        .check-mark {{
            color: #08796f;
            font-weight: 900;
            font-size: 10pt;
        }}

        /* FAQS */
        .faq-item {{
            margin-bottom: 12px;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .faq-item h4 {{
            font-size: 10pt;
            font-weight: 700;
            color: #143a35;
            margin-bottom: 3px;
        }}
        .faq-item p {{
            font-size: 9.2pt;
            color: #3d4a47;
            margin-bottom: 0;
            line-height: 1.5;
        }}

        /* SEARCH KEYWORDS PAGE */
        .keywords-page {{
            margin-top: 24px;
            padding-top: 8px;
        }}
        .keywords-page h2 {{
            font-size: 18pt;
            font-weight: 800;
            color: #143a35;
            margin-bottom: 6px;
        }}
        .keywords-subtitle {{
            font-size: 9.2pt;
            color: #53615e;
            margin-bottom: 18px;
            font-style: italic;
        }}
        ul.keywords-list {{
            list-style: none;
            padding: 0;
            column-count: 2;
            column-gap: 24px;
        }}
        ul.keywords-list li {{
            font-size: 9.2pt;
            color: #222928;
            margin-bottom: 8px;
            line-height: 1.4;
            break-inside: avoid;
        }}
    </style>
</head>
<body>

    <!-- ================= DOCUMENT HEADER & INTRO (NATURAL CONTINUOUS FLOW) ================= -->
    <!-- H1 TITLE (No labels) -->
    <h1 class="article-title">{title}</h1>

    <!-- META DESCRIPTION (No labels) -->
    <p class="meta-description">{meta_desc}</p>

    <!-- LARGE CENTERED PRODUCT HERO SHOWCASE (520px - COMPETITOR BENCHMARK) -->
    <div style="text-align: center; margin: 16px auto 18px auto;">
        <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener">
            <img src="{img1}" alt="{topic}" style="max-width: 520px; width: 100%; max-height: 290px; object-fit: contain; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.08); background: #ffffff; display: block; margin: 0 auto;" onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=600';">
        </a>
    </div>

    <!-- OBJECTIVE OPENING PARAGRAPHS -->
    <p>{data['intro_p1']}</p>
    <p>{data['intro_p2']}</p>

    <!-- FIRST PRIMARY PILL CTA BUTTON (Centered, clickable) -->
    <div class="cta-container" style="margin-top: 20px; margin-bottom: 20px;">
        <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="cta-pill-btn">
            Check Official {topic} Details
        </a>
    </div>

    <!-- GUARANTEED EXECUTIVE FACT SHEET & SPECS (ZERO BLANK SPACE) -->
    {data.get('exec_summary_html', '')}

    <!-- TABLE OF CONTENTS (Clickable Anchors) -->
    <div class="toc-container" style="margin-top: 14px;">
        <div class="toc-title">In this guide</div>
        <ul class="toc-list">
            {data['toc_html']}
        </ul>
    </div>

    <!-- ================= PAGES 3 - 8 ================= -->
    <!-- SECTION 1: WHAT IS IT -->
    <h2 class="sec-heading" id="what-is">What is {topic}? Understanding This {keyword}</h2>
    <p>{data['what_is_text']}</p>

    <!-- NATURAL SECONDARY CTA 1 -->
    <div class="cta-container">
        <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="cta-secondary-btn">
            View the Current Product Information
        </a>
    </div>

    <!-- SECTION 2: ARCHITECTURE & SPECS -->
    <h2 class="sec-heading" id="architecture">{data['sec2_heading']}</h2>
    <p>{data['sec2_text']}</p>

    <!-- SECTION 3: BENEFITS & LIMITATIONS -->
    <h2 class="sec-heading" id="benefits-limits">Potential Benefits and Realistic Limitations of {topic}</h2>
    <p>{data['benefits_limits_text']}</p>

    <!-- NATURAL SECONDARY CTA 2 -->
    <div class="cta-container">
        <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="cta-secondary-btn">
            Inspect the Official {topic} Details
        </a>
    </div>

    <!-- SECTION 4: SAFETY & STANDARDS -->
    <h2 class="sec-heading" id="safety-standards">Safety, Standards & Quality Verification for {topic}</h2>
    <p>{data['safety_standards_text']}</p>

    <!-- SECTION 5: PRICE & VALUE -->
    <h2 class="sec-heading" id="price-value">Price, Value, and Official Ordering Guidance for {topic}</h2>
    <p>{data['price_value_text']}</p>

    <!-- NATURAL SECONDARY CTA 3 -->
    <div class="cta-container">
        <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="cta-secondary-btn">
            See Current Pricing and Offers
        </a>
    </div>

    <!-- SECTION 6: COMPARISON -->
    <h2 class="sec-heading" id="comparison">How {topic} Compares with Leading {keyword} Alternatives</h2>
    <p>
        The most useful evaluation is not a popularity contest. It is a structured assessment of specifications, long-term durability, price-to-value ratio, and the specific needs of your daily routine:
    </p>
    {data['table_html']}

    <!-- NATURAL SECONDARY CTA 4 -->
    <div class="cta-container">
        <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="cta-secondary-btn">
            Compare the Official Offer
        </a>
    </div>

    <!-- SECTION 7: PROS & CONS -->
    <div class="pros-cons-section" id="pros-cons">
        <h2 class="sec-heading">Pros and Cons: {topic} {keyword} Strengths & Limitations</h2>
        
        <h3 class="sub-sec-heading">Potential Advantages</h3>
        <ul class="plain-bullets">
            {data['pros_html']}
        </ul>

        <h3 class="sub-sec-heading">Limitations to Consider</h3>
        <ul class="plain-bullets">
            {data['cons_html']}
        </ul>
    </div>

    <!-- SECTION 8: PRACTICAL BUYING CHECKLIST -->
    <div id="checklist">
        <h2 class="sec-heading">A Practical Buying Checklist for {topic} {keyword}</h2>
        <div class="checklist-box">
            <ul class="checklist">
                {data['checklist_html']}
            </ul>
        </div>
        <p style="font-size: 9.5pt; color: #53615e; font-style: italic;">
            A responsible buying decision is not simply: "Does the marketing sound convincing?" It is: "Do I understand what I am purchasing, what it costs over time, and what verified evidence supports it?"
        </p>
    </div>

    <!-- NATURAL SECONDARY CTA 5 -->
    <div class="cta-container">
        <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="cta-secondary-btn">
            Review Official Terms Before Buying
        </a>
    </div>

    <!-- SECTION 9: FAQS (10 FAQS) -->
    <div id="faqs">
        <h2 class="sec-heading">Frequently Asked Questions: {topic} {keyword}</h2>
        {data['faqs_html']}
    </div>

    <!-- SECTION 10: FINAL ASSESSMENT & VERDICT -->
    <div id="verdict" style="margin-top: 24px;">
        <h2 class="sec-heading">Final Assessment: Is {topic} {keyword} Worth Buying?</h2>
        <p>{data['final_verdict_text']}</p>
        
        <!-- FINAL CTA PILL BUTTON -->
        <div class="cta-container" style="margin-top: 20px;">
            <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="cta-pill-btn">
                Check Official {topic} Details
            </a>
        </div>
    </div>

</body>
</html>
"""
    return html

def generate_reality_check_pdf_html(data: Dict[str, Any], button_color: str = "#2563eb") -> str:
    """
    Renders the Modern Medical Reality Check visual layout (Nitric Boost Style):
    - Top Medical Trust Header (Clinical Research Team, Publication Date, FDA/GMP badge).
    - Alternating vibrant accent cards (Soft Blue, Mint, Amber with left border bars).
    - High-converting gradient CTA pill buttons with trust sub-lines.
    - Full E-E-A-T SEO structure: Table of Contents, Comparison Table, Pros/Cons, Checklist, 10 FAQs.
    - Page 10 Orange Dashed Limited-Offer Mega Deal Callout Box.
    - Dedicated Search Keywords & Editorial Index page.
    """
    title = data["title"]
    meta_desc = data["meta_desc"]
    affiliate_url = data["affiliate_url"]
    topic = data["topic"]
    topic_upper = data["topic_upper"]
    keyword = data["keyword"]
    img1 = data["img1"]
    current_date = time.strftime("%B %d, %Y")
    theme_primary = data.get("theme_primary") or "#1e40af"
    theme_accent = data.get("theme_accent") or button_color or "#2563eb"
    theme_light_tint = data.get("theme_light_tint") or "#eff6ff"
    theme_border_tint = data.get("theme_border_tint") or "#dbeafe"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <meta name="description" content="{meta_desc}">
    <style>
        @page {{
            size: A4 portrait;
            margin: 14mm 16mm 18mm 16mm;
            @bottom-left {{
                content: "{topic_upper}  |  REALITY CHECK 2026";
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 8pt;
                color: #64748b;
                border-top: 1px solid {theme_border_tint};
                padding-top: 5px;
            }}
            @bottom-right {{
                content: "Page " counter(page);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 8pt;
                color: #64748b;
                border-top: 1px solid {theme_border_tint};
                padding-top: 5px;
            }}
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #1e293b;
            background: #ffffff;
            line-height: 1.62;
            font-size: 9.8pt;
        }}

        .page-break-after {{
            page-break-after: always;
            break-after: page;
        }}
        .page-break-before {{
            page-break-before: always;
            break-before: page;
        }}
        .no-break {{
            page-break-inside: avoid;
            break-inside: avoid;
        }}

        /* TOP MEDICAL TRUST HEADER */
        h1.rc-main-title {{
            font-size: 19pt;
            font-weight: 800;
            color: {theme_primary};
            line-height: 1.25;
            margin-bottom: 12px;
            letter-spacing: -0.3px;
        }}


        .rc-hero-bar {{
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 16px;
        }}
        .rc-hero-thumb {{
            width: 75px;
            height: 75px;
            object-fit: contain;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
            padding: 4px;
            background: #ffffff;
        }}
        .rc-hero-text h2 {{
            font-size: 13.5pt;
            font-weight: 800;
            color: {theme_primary};
            line-height: 1.25;
        }}
        .rc-hero-text p {{
            font-size: 8.8pt;
            color: #64748b;
            margin-top: 3px;
        }}

        /* HEADINGS */
        h2.rc-sec-title {{
            font-size: 14pt;
            font-weight: 800;
            color: {theme_primary};
            margin-top: 18px;
            margin-bottom: 8px;
            line-height: 1.3;
            page-break-after: avoid;
            break-after: avoid;
        }}

        h3.rc-sub-title {{
            font-size: 11pt;
            font-weight: 700;
            color: {theme_accent};
            margin-top: 10px;
            margin-bottom: 6px;
        }}

        /* ACCENT CARDS */
        .rc-card {{
            border-radius: 6px;
            padding: 14px 18px;
            margin: 12px 0;
        }}
        .rc-card-blue {{
            background: {theme_light_tint};
            border-left: 4.5px solid {theme_accent};
        }}
        .rc-card-amber {{
            background: #fffbeb;
            border-left: 4.5px solid #f59e0b;
        }}
        .rc-card-green {{
            background: #f0fdf4;
            border-left: 4.5px solid #16a34a;
        }}
        .rc-card-purple {{
            background: #faf5ff;
            border-left: 4.5px solid #9333ea;
        }}

        p {{
            margin-bottom: 10px;
            text-align: justify;
            color: #334155;
            font-size: 9.8pt;
        }}

        strong {{
            color: #0f172a;
            font-weight: 700;
        }}

        /* HERO GRAPHIC BANNER */
        .rc-hero-banner {{
            text-align: center;
            margin: 10px 0 14px 0;
        }}
        .rc-hero-banner-img {{
            max-width: 100%;
            height: 190px;
            object-fit: cover;
            border-radius: 8px;
            border: 1px solid #cbd5e1;
        }}

        /* CTA BUTTONS */
        .rc-cta-wrap {{
            text-align: center;
            margin: 14px 0 16px 0;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .rc-btn {{
            display: inline-block;
            padding: 11px 30px;
            border-radius: 26px;
            font-weight: 800;
            font-size: 10pt;
            text-decoration: none !important;
            color: #ffffff !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        .rc-btn-blue {{ background: linear-gradient(135deg, {theme_primary} 0%, {theme_accent} 100%); }}
        .rc-btn-amber {{ background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }}
        .rc-btn-green {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); }}
        .rc-btn-pink {{ background: linear-gradient(135deg, #ec4899 0%, #be185d 100%); }}
        .rc-btn-purple {{ background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%); }}
        .rc-btn-orange {{ background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); }}
        .rc-btn-coral {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }}

        .rc-trust-subline {{
            font-size: 8pt;
            color: #b45309;
            font-weight: 700;
            margin-top: 5px;
            letter-spacing: 0.2px;
        }}

        /* PAGE 2 TOC */
        .rc-visual-img {{
            max-width: 260px;
            max-height: 260px;
            object-fit: contain;
            border-radius: 6px;
            border: 1px solid #cbd5e1;
            padding: 8px;
            background: #ffffff;
            display: block;
            margin: 0 auto;
        }}
        .rc-visual-caption {{
            font-size: 8.5pt;
            color: #64748b;
            margin-top: 6px;
            font-style: italic;
            text-align: center;
        }}

        .rc-toc-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .rc-toc-list li {{
            margin-bottom: 7px;
            font-size: 9.5pt;
        }}
        .rc-toc-list a {{
            color: {theme_primary};
            text-decoration: none;
            font-weight: 600;
        }}
        .rc-toc-list a:hover {{
            text-decoration: underline;
        }}

        /* COMPARISON TABLE */
        table.rc-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 8.8pt;
            margin: 10px 0;
        }}
        table.rc-table tr {{
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        table.rc-table th, table.rc-table td {{
            padding: 9px 12px;
            border: 1px solid #cbd5e1;
            text-align: left;
            vertical-align: top;
        }}
        table.rc-table th {{
            background: {theme_primary};
            color: #ffffff;
            font-weight: 700;
            font-size: 9pt;
        }}
        table.rc-table tr:nth-child(even) {{
            background: #f8fafc;
        }}

        /* PROS & CONS */
        ul.rc-bullets {{
            list-style: none;
            padding: 0;
            margin-bottom: 10px;
        }}
        ul.rc-bullets li {{
            font-size: 9.2pt;
            color: #1e293b;
            margin-bottom: 5px;
            line-height: 1.4;
        }}

        /* CHECKLIST */
        ul.rc-checklist {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        ul.rc-checklist li {{
            font-size: 9.2pt;
            color: #1e293b;
            margin-bottom: 6px;
            display: flex;
            align-items: flex-start;
            gap: 6px;
            line-height: 1.4;
        }}
        .rc-check-symbol {{
            color: #16a34a;
            font-weight: 900;
        }}

        /* FAQS */
        .rc-faq-item {{
            margin-bottom: 10px;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .rc-faq-item h4 {{
            font-size: 9.8pt;
            font-weight: 700;
            color: {theme_primary};
            margin-bottom: 3px;
        }}
        .rc-faq-item p {{
            font-size: 9pt;
            color: #475569;
            margin-bottom: 0;
        }}

        /* PAGE 10 MEGA DEAL BOX */
        .rc-mega-deal-box {{
            border: 2.5px dashed {theme_primary};
            background: {theme_light_tint};
            border-radius: 12px;
            padding: 22px 20px;
            text-align: center;
            margin: 20px 0;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .rc-mega-deal-title {{
            font-size: 18pt;
            font-weight: 900;
            color: {theme_primary};
            margin-bottom: 6px;
        }}
        .rc-mega-deal-sub {{
            font-size: 10pt;
            color: #475569;
            margin-bottom: 14px;
            font-weight: 500;
        }}
        .rc-mega-deal-btn {{
            display: inline-block;
            background: linear-gradient(135deg, {theme_primary} 0%, {theme_accent} 100%);
            color: #ffffff !important;
            font-size: 11pt;
            font-weight: 900;
            padding: 13px 34px;
            border-radius: 8px;
            text-decoration: none !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
            text-transform: uppercase;
        }}
        .rc-mega-deal-guarantee {{
            font-size: 8.5pt;
            color: #15803d;
            font-weight: 700;
            margin-top: 10px;
        }}

        /* KEYWORDS INDEX */
        .rc-keywords-wrap {{
            margin-top: 24px;
            padding-top: 10px;
        }}
        .rc-keywords-wrap h2 {{
            font-size: 17pt;
            font-weight: 800;
            color: {theme_primary};
            margin-bottom: 4px;
        }}
        .rc-keywords-sub {{
            font-size: 8.8pt;
            color: #64748b;
            margin-bottom: 14px;
            font-style: italic;
        }}
        ul.rc-kw-list {{
            list-style: none;
            padding: 0;
            column-count: 2;
            column-gap: 20px;
        }}
        ul.rc-kw-list li {{
            font-size: 9pt;
            color: #334155;
            margin-bottom: 6px;
            break-inside: avoid;
        }}
    </style>
</head>
<body>

    <!-- ================= DOCUMENT HEADER & INTRO (NATURAL FLOW - ZERO BLANK SPACE) ================= -->
    <!-- TOP DOCUMENT TITLE -->
    <h1 class="rc-main-title">{title}</h1>

    <!-- DOCUMENT META SUMMARY -->
    <p style="font-size: 10pt; color: #475569; margin: 10px 0 14px 0; line-height: 1.5; font-style: italic;">{meta_desc}</p>

    <!-- INTRODUCTION HEADING -->
    <h2 class="rc-sec-title">Introduction</h2>

    <!-- LARGE CENTERED PRODUCT HERO SHOWCASE (540px - PROMINENT & HIGH-RES) -->
    <div style="text-align: center; margin: 14px auto 16px auto;">
        <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener">
            <img src="{img1}" alt="{topic}" style="max-width: 540px; width: 100%; max-height: 320px; object-fit: contain; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.09); background: #ffffff; display: block; margin: 0 auto;" onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=600';">
        </a>
    </div>

    <!-- BLUE ACCENT CARD WITH HERO CONTENT -->
    <div class="rc-card rc-card-blue">
        <p>{data['intro_p1']}</p>
        <p>{data['intro_p2']}</p>
    </div>

    <!-- PRIMARY HERO CTA BUTTON -->
    <div class="rc-cta-wrap">
        <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="rc-btn rc-btn-blue">
            CLAIM EXCLUSIVE DISCOUNT TODAY
        </a>
        <div class="rc-trust-subline">Official Site • Free Shipping • {data.get('guarantee_days', 60)}-Day Guarantee</div>
    </div>

    <!-- GUARANTEED EXECUTIVE FACT SHEET & SPECS (ZERO BLANK SPACE) -->
    {data.get('exec_summary_html', '')}

    <!-- AMBER CARD: TABLE OF CONTENTS -->
    <div class="rc-card rc-card-amber" style="margin-top: 14px;">
        <h2 class="rc-sec-title" style="margin-top: 0; color: #b45309;">In this guide</h2>
        <ul class="rc-toc-list">
            {data['toc_html']}
        </ul>
    </div>

    <!-- SECTION 1: WHAT IS IT (MINT CARD) -->
    <h2 class="rc-sec-title" id="what-is" style="margin-top: 16px;">What is {topic}? Understanding This {keyword}</h2>
    <div class="rc-card rc-card-green">
        <p>{data['what_is_text']}</p>
    </div>

    <!-- SECTION 2: ARCHITECTURE & SPECS (BLUE CARD) -->
    <h2 class="rc-sec-title" id="architecture">{data['sec2_heading']}</h2>
    <div class="rc-card rc-card-blue">
        <p>{data['sec2_text']}</p>
    </div>

    <!-- SECTION 3: BENEFITS & LIMITATIONS (AMBER CARD) -->
    <h2 class="rc-sec-title" id="benefits-limits">Potential Benefits and Realistic Limitations of {topic}</h2>
    <div class="rc-card rc-card-amber">
        <p>{data['benefits_limits_text']}</p>
        <div class="rc-cta-wrap" style="margin-top: 14px;">
            <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="rc-btn rc-btn-orange">
                ORDER {topic_upper} AT LOWEST PRICE
            </a>
            <div class="rc-trust-subline">Official Site • Free Shipping • {data.get('guarantee_days', 60)}-Day Guarantee</div>
        </div>
    </div>

    <!-- SECTION 4: SAFETY & STANDARDS (MINT CARD) -->
    <h2 class="rc-sec-title" id="safety-standards">Safety, Standards & Quality Verification for {topic}</h2>
    <div class="rc-card rc-card-green">
        <p>{data['safety_standards_text']}</p>
    </div>

    <!-- SECTION 5: PRICE & VALUE (BLUE CARD - INCLUDES PRICING, BONUSES & HIGH-INTENT OFFER CTA) -->
    <h2 class="rc-sec-title" id="price-value">Price, Value, and Official Ordering Guidance for {topic}</h2>
    <div class="rc-card rc-card-blue">
        <p>{data['price_value_text']}</p>
    </div>

    <!-- SECTION 6: COMPARISON (ROYAL BLUE TABLE IN CARD) -->
    <h2 class="rc-sec-title" id="comparison">How {topic} Compares with Leading {keyword} Alternatives</h2>
    <div class="rc-card rc-card-blue">
        <p>
            The most useful evaluation is not a popularity contest. It is a structured assessment of specifications, long-term durability, price-to-value ratio, and the specific needs of your daily routine:
        </p>
        {data['table_html']}
    </div>

    <!-- SECTION 7: PROS & CONS (MINT CARD) -->
    <div id="pros-cons">
        <h2 class="rc-sec-title">Pros and Cons: {topic} {keyword} Strengths & Limitations</h2>
        <div class="rc-card rc-card-green">
            <h3 class="rc-sub-title" style="color: #15803d;">Potential Advantages</h3>
            <ul class="rc-bullets">
                {data['pros_html']}
            </ul>
            <h3 class="rc-sub-title" style="color: #b91c1c; margin-top: 12px;">Limitations to Consider</h3>
            <ul class="rc-bullets">
                {data['cons_html']}
            </ul>
        </div>
    </div>

    <!-- SECTION 8: PRACTICAL BUYING CHECKLIST (AMBER CARD) -->
    <div id="checklist">
        <h2 class="rc-sec-title">A Practical Buying Checklist for {topic} {keyword}</h2>
        <div class="rc-card rc-card-amber">
            <ul class="rc-checklist">
                {data['checklist_html']}
            </ul>
            <p style="font-size: 8.8pt; color: #b45309; font-style: italic; margin-top: 10px;">
                A responsible buying decision is not simply: "Does the marketing sound convincing?" It is: "Do I understand what I am purchasing, what it costs over time, and what verified evidence supports it?"
            </p>
        </div>
    </div>

    <div class="rc-cta-wrap">
        <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="rc-btn rc-btn-blue">
            BUY FROM OFFICIAL SITE ONLY
        </a>
        <div class="rc-trust-subline">Official Site • Free Shipping • {data.get('guarantee_days', 60)}-Day Guarantee</div>
    </div>

    <!-- SECTION 9: FAQS (BLUE CARD) -->
    <div id="faqs">
        <h2 class="rc-sec-title">Frequently Asked Questions: {topic} {keyword}</h2>
        <div class="rc-card rc-card-blue">
            {data['faqs_html']}
        </div>
    </div>

    <!-- SECTION 10: FINAL ASSESSMENT (AMBER CARD) -->
    <div id="verdict" style="margin-top: 18px;">
        <h2 class="rc-sec-title">Final Assessment: Is {topic} {keyword} Worth Buying?</h2>
        <div class="rc-card rc-card-amber">
            <p>{data['final_verdict_text']}</p>
        </div>
    </div>

    <!-- ================= NATURAL FLOW: MEGA DEAL BOX & KEYWORDS ================= -->
    <div style="margin-top: 20px;">
        <!-- ICONIC ORANGE DASHED MEGA DEAL BOX -->
        <div class="rc-mega-deal-box">
            <h2 class="rc-mega-deal-title">Special Limited Offer Available!</h2>
            <p class="rc-mega-deal-sub">Join thousands who have already transformed their health with {topic}</p>
            <div style="margin: 18px 0;">
                <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="rc-mega-deal-btn">
                    GET {topic_upper} AT EXCLUSIVE DISCOUNT NOW
                </a>
            </div>
            <div class="rc-mega-deal-guarantee">
                ✅ {data.get('guarantee_days', 60)}-Day Money Back Guarantee • Free Worldwide Shipping • Secure Checkout
            </div>
            <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px 16px; margin-top: 16px; font-size: 8.5pt; color: #475569; line-height: 1.5; text-align: left;">
                <strong style="color: #1e293b; display: block; margin-bottom: 3px;">Editorial & Clinical Advisory:</strong>
                This independent review is compiled for educational and consumer guidance. Dietary supplements are not evaluated by the FDA to treat, diagnose, cure, or prevent any disease. Always consult your physician before starting any supplementation protocol, especially if taking prescription medications.
            </div>
            <div style="margin-top: 16px;">
                <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="rc-btn rc-btn-blue" style="font-size: 9pt; padding: 8px 22px;">
                    DON'T MISS THIS LIMITED DEAL
                </a>
            </div>
        </div>
    </div>

</body>
</html>
"""
    return html

def convert_html_to_master_pdf(html_content: str, output_path: str) -> str:
    """
    Renders the Authority Magazine HTML into a vector clickable PDF using Playwright Chromium.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        page = browser.new_page()

        page.set_content(html_content, wait_until="load", timeout=30000)

        page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "0px", "bottom": "0px", "left": "0px", "right": "0px"}
        )
        browser.close()

    return output_path

def inject_google_pdf_metadata(
    pdf_path: str,
    title: str,
    meta_desc: str,
    keywords: List[str],
    author: str = "Independent Editorial Research"
) -> str:
    """
    Directly writes Google-compliant metadata dictionary (/Title, /Subject, /Keywords, /Author)
    into the binary PDF using pypdf.
    Google Search Engine uses /Title for the SERP blue link and /Subject for the 150-160 char snippet.
    """
    temp_path = pdf_path + ".tmp.pdf"
    reader = pypdf.PdfReader(pdf_path)
    writer = pypdf.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    metadata = {
        "/Title": title,
        "/Subject": meta_desc,  # Google uses /Subject as the search snippet (Meta Description)
        "/Keywords": ", ".join(keywords),
        "/Author": author,
        "/Creator": "Google Authority PDF Editorial Engine",
        "/Producer": "Google Search Verified PDF Compiler"
    }
    writer.add_metadata(metadata)

    with open(temp_path, "wb") as f_out:
        writer.write(f_out)

    os.replace(temp_path, pdf_path)
    return pdf_path

def process_master_pdf_single_product(
    keyword: str,
    affiliate_url: str,
    output_dir: str,
    topic: str = "",
    brand_name: str = "",
    angle_idx: int = 0,
    category: str = "auto",
    template: str = "reality_check",
    image_url_1: str = "",
    image_url_2: str = "",
    image_url_3: str = "",
    button_color: str = "#2563eb",
    pasted_text: Optional[str] = None,
    scraped_data: Optional[Dict[str, Any]] = None,
    custom_title: str = "",
    secondary_keywords: str = "",
    theme_primary: str = "",
    theme_accent: str = ""
) -> str:
    """
    Generates a 100% unique, human-style SEO PDF for a single product based on angle_idx
    with selectable templates (Medical Reality Check vs Authority Buying Guide) and Google PDF metadata injection.
    """
    archetype = ANGLE_ARCHETYPES[angle_idx % len(ANGLE_ARCHETYPES)]
    resolved_category = detect_category(topic=topic, keyword=keyword, explicit_choice=category)

    data = build_unique_article_content_for_angle(
        keyword=keyword,
        affiliate_url=affiliate_url,
        topic=topic,
        brand_name=brand_name,
        angle_idx=angle_idx,
        category=resolved_category,
        image_url_1=image_url_1,
        image_url_2=image_url_2,
        image_url_3=image_url_3,
        pasted_text=pasted_text if angle_idx == 0 else None,
        scraped_data=scraped_data,
        custom_title=custom_title,
        secondary_keywords=secondary_keywords,
        theme_primary=theme_primary,
        theme_accent=theme_accent
    )

    if template == "joint_genesis":
        html = generate_master_pdf_html(data, button_color=button_color)
    else:
        html = generate_reality_check_pdf_html(data, button_color=button_color)

    pdf_filename = build_seo_filename(
        topic=topic or keyword,
        keyword=keyword or topic,
        angle_slug=archetype["id"],
        vol_num=angle_idx + 1
    )
    pdf_path = os.path.join(output_dir, pdf_filename)

    # 1. Render vector PDF
    convert_html_to_master_pdf(html, pdf_path)

    # 2. Inject Google Search Engine Metadata (/Title, /Subject, /Keywords, /Author)
    inject_google_pdf_metadata(
        pdf_path=pdf_path,
        title=data["title"],
        meta_desc=data["meta_desc"],
        keywords=data["keywords_list"],
        author=f"{data['brand']} Research & Editorial Team"
    )

    return pdf_path
