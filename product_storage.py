import os
import json
from typing import Dict, Any, List

STORAGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_products.json")

DEFAULT_PRODUCTS: Dict[str, Dict[str, Any]] = {}

def load_saved_products() -> Dict[str, Dict[str, Any]]:
    """Loads all saved products from disk."""
    if not os.path.exists(STORAGE_FILE):
        save_all_products({})
        return {}
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception:
        return {}

def save_all_products(products: Dict[str, Dict[str, Any]]) -> bool:
    """Saves the entire product dictionary to saved_products.json."""
    try:
        tmp_file = f"{STORAGE_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        if os.path.exists(STORAGE_FILE):
            os.remove(STORAGE_FILE)
        os.rename(tmp_file, STORAGE_FILE)
        return True
    except Exception:
        return False

def save_or_update_product(
    product_name: str,
    affiliate_url: str,
    primary_keyword: str,
    secondary_keywords: str = "",
    brand_name: str = "",
    category: str = "auto",
    theme_primary: str = "#1e40af",
    theme_accent: str = "#2563eb"
) -> bool:
    """Adds or updates a single product in the persistent store."""
    name_clean = product_name.strip()
    if not name_clean:
        return False
    products = load_saved_products()
    products[name_clean] = {
        "product_name": name_clean,
        "affiliate_url": affiliate_url.strip(),
        "primary_keyword": primary_keyword.strip(),
        "secondary_keywords": secondary_keywords.strip(),
        "brand_name": brand_name.strip(),
        "category": category,
        "theme_primary": theme_primary.strip() or "#1e40af",
        "theme_accent": theme_accent.strip() or "#2563eb"
    }
    return save_all_products(products)

def delete_product(product_name: str) -> bool:
    """Deletes a product by name."""
    products = load_saved_products()
    if product_name in products:
        del products[product_name]
        return save_all_products(products)
    return False

def generate_title_recommendations(product_name: str, keyword: str, style_variation: int = 0) -> List[str]:
    """Generates 5 distinct high-converting SEO title recommendations based on product & keyword."""
    p = product_name.strip() or "Product"
    k = keyword.strip() or f"{p} Review"

    variations = [
        # Standard Set
        [
            f"{p} Review 2026: Clinical Ingredients, Evidence & Honest Buying Guide",
            f"{p} Complete Buyer's Guide: Packages, Pricing, Bonuses & Official Link",
            f"{p} Honest Breakdown: 7 Standout Benefits vs Real Limitations",
            f"{p} vs Leading Market Alternatives: Head-to-Head Comparison & Real Differences",
            f"Is {p} Worth the Money? Package Breakdown, Real ROI & Buying Guide"
        ],
        # Hook/Curiosity Set
        [
            f"{p} ({k}): Shocking Truth, Medical Analysis & Clinical Reality Check",
            f"The Ultimate 2026 {p} Buyer's Blueprint: Pricing, Discounts & Purity Audit",
            f"{p} Pros and Cons Uncovered: What They Won't Tell You Before Buying",
            f"{p} Benchmark Matrix: Why It Outperforms Competitor Formulations",
            f"Don't Buy {p} Until You Read This: Package Deals & 60-Day Guarantee Test"
        ],
        # Direct Action Set
        [
            f"{p} Clinical Report: Laboratory Purity Standards & 30-Day Results",
            f"Official 2026 {p} Pricing Guide: Where to Order Genuine Batch & Claim Bonuses",
            f"{p} Reality Check: Critical Safety Profile, Dosage Protocol & Limitations",
            f"How {p} Compares to Standard Alternatives: In-Depth Ingredient Showdown",
            f"{p} Value Assessment: Exclusive Manufacturer Packages & Final Scorecard"
        ]
    ]

    var_idx = style_variation % len(variations)
    return variations[var_idx]
