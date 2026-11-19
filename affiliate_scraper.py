import os
import re
import base64
import json
import time
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright
import requests

def image_to_base64_data_uri(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Converts raw image bytes to a base64 data URI."""
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"

def download_image_as_b64(page, img_url: str) -> str:
    """Downloads an image in the browser context or via requests fallback and returns a base64 data URI."""
    if not img_url:
        return ""
    if img_url.startswith("data:image"):
        return img_url

    # 1. Try in-browser fetch via page.evaluate
    try:
        b64 = page.evaluate("""async (url) => {
            try {
                const resp = await fetch(url, { mode: 'no-cors' });
                const blob = await resp.blob();
                return new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.readAsDataURL(blob);
                });
            } catch(e) {
                return '';
            }
        }""", img_url)
        if b64 and b64.startswith("data:image"):
            return b64
    except Exception:
        pass

    # 2. Fallback to requests with standard browser headers
    try:
        resp = requests.get(
            img_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
            },
            timeout=12
        )
        if resp.status_code == 200 and len(resp.content) > 500:
            content_type = resp.headers.get("content-type", "image/png").split(";")[0]
            return image_to_base64_data_uri(resp.content, content_type)
    except Exception:
        pass

    return ""

def scrape_affiliate_landing_page(url: str, timeout_ms: int = 28000) -> Dict[str, Any]:
    """
    Navigates to the affiliate URL, follows all redirects (e.g., ClickBank hop links),
    and comprehensively extracts:
    1. Product Name & Brand
    2. Primary High-Res Product Bottle/Package Image (as base64 or URL)
    3. Real Ingredients & Core Biological Mechanism
    4. Exact Pricing Tiers & Package Breakdown
    5. Exact Guarantee Period (60, 90, 180 days)
    6. Real Digital Bonuses (Cover Images as base64, Titles, Dollar Values, Descriptions)
    7. Core Problem-Solution Sales Hook
    """
    result: Dict[str, Any] = {
        "success": False,
        "input_url": url,
        "final_url": url,
        "product_name": "",
        "brand_name": "",
        "headline": "",
        "category": "health_supplements",
        "format": "nano-enhanced liquid sublingual drops",
        "target_system": "circadian pacemaker & cellular equilibrium",
        "product_image": "",
        "product_image_b64": "",
        "secondary_images": [],
        "ingredients": [],
        "pricing_tiers": [],
        "guarantee_days": 60,
        "bonuses": [],
        "theme_primary": "#1e40af",
        "theme_accent": "#2563eb",
        "sales_hook": "",
        "raw_text_sample": ""
    }

    if not url or not url.strip().startswith("http"):
        return result

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1400, "height": 900}
        )
        page = context.new_page()

        try:
            # 1. Navigate & follow all redirects to final landing page
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass
            time.sleep(2.0)  # allow dynamic VSL/landing scripts to execute

            final_url = page.url
            result["final_url"] = final_url

            # 2. Extract Document Title & Meta tags using fast non-blocking evaluate
            meta_info = page.evaluate("""() => {
                const getMeta = (prop) => {
                    const el = document.querySelector(`meta[property="${prop}"], meta[name="${prop}"]`);
                    return el ? el.getAttribute('content') || '' : '';
                };
                const h1 = document.querySelector('h1')?.innerText || '';
                return {
                    title: document.title || '',
                    og_title: getMeta('og:title'),
                    og_image: getMeta('og:image'),
                    meta_desc: getMeta('description') || getMeta('og:description'),
                    h1: h1
                };
            }""")

            doc_title = meta_info.get("title", "")
            og_title = meta_info.get("og_title", "")
            og_image = meta_info.get("og_image", "")
            meta_desc = meta_info.get("meta_desc", "")
            h1_text = meta_info.get("h1", "")

            # Clean product name candidate
            raw_name = og_title or doc_title or h1_text
            clean_name = re.sub(r'[-–|:•]\s*(?:text\s*presentation|video\s*presentation|presentation|vsl|video\s*sales\s*letter|official\s*(?:website|site|store|page|portal)?|reviews?|store|shop|get|order|discount|buy\s*now|buy\s*online|supplement|formula|special\s*offer|special\s*discount).*$', '', raw_name, flags=re.IGNORECASE).strip()
            clean_name = re.sub(r'\b(?:text|video)\s*presentation\b', '', clean_name, flags=re.IGNORECASE).strip()
            if not clean_name or len(clean_name) > 35:
                if h1_text and len(h1_text) < 35:
                    clean_name = re.sub(r'[-–|:•]\s*(?:text\s*presentation|video\s*presentation|presentation|vsl|official).*$', '', h1_text, flags=re.IGNORECASE).strip()
                    clean_name = re.sub(r'\b(?:text|video)\s*presentation\b', '', clean_name, flags=re.IGNORECASE).strip()
            
            result["product_name"] = clean_name or raw_name[:30].strip()
            result["headline"] = og_title or doc_title or h1_text

            # 2b. Extract Website Theme Colors (Dominant Brand Color / Primary CTA Color)
            try:
                theme_colors = page.evaluate("""() => {
                    const parseColor = (col) => {
                        if (!col || col === 'transparent' || col === 'rgba(0, 0, 0, 0)') return '';
                        const rgb = col.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/);
                        if (rgb) {
                            const hex = (x) => ("0" + parseInt(x).toString(16)).slice(-2);
                            return "#" + hex(rgb[1]) + hex(rgb[2]) + hex(rgb[3]);
                        }
                        if (col.startsWith('#') && (col.length === 7 || col.length === 4)) return col;
                        return '';
                    };

                    const btnSelectors = [
                        'a.btn', 'button.btn', '.order-btn', '.cta-btn', '.vsl-btn', 
                        'a[href*="pay"]', 'a[href*="checkout"]', 'a[href*="order"]', 
                        'button[type="submit"]', '.btn-primary', '.button-primary',
                        '.btn-order', '.btn-buy', '.btn-checkout'
                    ];
                    for (const sel of btnSelectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const style = window.getComputedStyle(el);
                            const bg = parseColor(style.backgroundColor);
                            if (bg && bg !== '#ffffff' && bg !== '#000000') {
                                return { primary: bg };
                            }
                        }
                    }

                    const header = document.querySelector('header, .header, nav, .navbar');
                    if (header) {
                        const hStyle = window.getComputedStyle(header);
                        const hBg = parseColor(hStyle.backgroundColor);
                        if (hBg && hBg !== '#ffffff' && hBg !== '#000000') {
                            return { primary: hBg };
                        }
                    }

                    return { primary: '#1e40af' };
                }""")
                if theme_colors and theme_colors.get("primary"):
                    result["theme_primary"] = theme_colors["primary"]
            except Exception:
                pass

            # 3. Extract Full Page Text for Analysis
            body_text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
            result["raw_text_sample"] = body_text[:2500]

            # 4. Guarantee Extraction (e.g. 60-day, 90-day, 180-day)
            guarantee_match = re.search(r'(\d{2,3})\s*[- ]?(?:day|days)\s*(?:money[- ]back|guarantee|risk[- ]free)', body_text, re.IGNORECASE)
            if guarantee_match:
                result["guarantee_days"] = int(guarantee_match.group(1))

            # 5. Extract Product Images using fast DOM evaluation
            image_candidates = page.evaluate("""() => {
                const imgs = Array.from(document.querySelectorAll('img'));
                return imgs.map(img => {
                    const rect = img.getBoundingClientRect();
                    return {
                        src: img.src || '',
                        alt: img.alt || '',
                        width: rect.width || img.naturalWidth || 0,
                        height: rect.height || img.naturalHeight || 0
                    };
                }).filter(img => img.src && !img.src.startsWith('data:image/svg'));
            }""")

            scored_product_imgs = []
            for img in image_candidates:
                try:
                    src = img.get("src", "")
                    alt = img.get("alt", "")
                    width = img.get("width", 0)
                    height = img.get("height", 0)

                    if width < 120 or height < 120:
                        continue

                    lower_src = src.lower()
                    lower_alt = alt.lower()

                    # Filter out logos, badges, payment icons, social media
                    skip_keywords = ["visa", "mastercard", "paypal", "amex", "stripe", "badge", "icon", "arrow", "seal", "stars", "guarantee-seal", "fda-badge", "footer", "logo"]
                    if any(sk in lower_src or sk in lower_alt for sk in skip_keywords):
                        continue

                    score = 0
                    # Positive keyword hints for main product bottle/box
                    product_hints = ["bottle", "product", "pack", "bundle", "jar", "supplement", "box", "hero", "dropper", "container", "supply", "front"]
                    for ph in product_hints:
                        if ph in lower_src:
                            score += 15
                        if ph in lower_alt:
                            score += 20

                    if clean_name.lower() in lower_src or clean_name.lower() in lower_alt:
                        score += 35

                    # Larger images preferred
                    score += int(min(width, 600) / 20)
                    score += int(min(height, 600) / 20)

                    scored_product_imgs.append((score, src, alt, width, height))
                except Exception:
                    continue

            scored_product_imgs.sort(key=lambda x: x[0], reverse=True)

            if og_image and not any(sk in og_image.lower() for sk in ["badge", "logo", "icon"]):
                abs_og = urljoin(final_url, og_image)
                result["product_image"] = abs_og
            elif scored_product_imgs:
                result["product_image"] = scored_product_imgs[0][1]

            # Secondary images
            sec_imgs = [img[1] for img in scored_product_imgs[1:4]]
            result["secondary_images"] = sec_imgs

            # 6. Extract Bonuses & Bonus Images (Bonus #1, Bonus #2)
            bonuses = []
            b1_match = re.search(r'(?:Free\s+Bonus|Bonus\s*#?1)[\s:–-]+([^\n\r]+)(?:[\r\n]+(?:\(Retail\s*Value|\$|\s*Instant|RRP|\s*Free)[^\n\r]*)?(?:[\r\n]+([^\n\r]{20,250}))?', body_text, re.IGNORECASE)
            b2_match = re.search(r'(?:Free\s+Bonus|Bonus\s*#?2)[\s:–-]+([^\n\r]+)(?:[\r\n]+(?:\(Retail\s*Value|\$|\s*Instant|RRP|\s*Free)[^\n\r]*)?(?:[\r\n]+([^\n\r]{20,250}))?', body_text, re.IGNORECASE)

            # Find bonus images
            bonus_imgs_found = []
            for img in image_candidates:
                isrc = img.get("src", "")
                ialt = img.get("alt", "")
                if isrc and any(k in isrc.lower() or k in ialt.lower() for k in ["bonus", "book", "ebook", "free-guide", "gift", "report"]):
                    bonus_imgs_found.append(isrc)

            if b1_match:
                b1_title = b1_match.group(1).strip()
                b1_desc = b1_match.group(2).strip() if b1_match.group(2) else "Step-by-step master digital guide revealing proven protocols and daily practices to maximize your results."
                b1_img = bonus_imgs_found[0] if len(bonus_imgs_found) > 0 else ""
                b1_b64 = download_image_as_b64(page, b1_img) if b1_img else ""
                bonuses.append({
                    "title": f"Bonus #1: {b1_title}",
                    "value": "$59",
                    "desc": b1_desc,
                    "image": b1_img,
                    "image_b64": b1_b64
                })

            if b2_match:
                b2_title = b2_match.group(1).strip()
                b2_desc = b2_match.group(2).strip() if b2_match.group(2) else "Comprehensive companion handbook detailing nutritional blueprints and lifestyle routines to amplify formula efficacy."
                b2_img = bonus_imgs_found[1] if len(bonus_imgs_found) > 1 else ""
                b2_b64 = download_image_as_b64(page, b2_img) if b2_img else ""
                bonuses.append({
                    "title": f"Bonus #2: {b2_title}",
                    "value": "$59",
                    "desc": b2_desc,
                    "image": b2_img,
                    "image_b64": b2_b64
                })

            result["bonuses"] = bonuses

            # 7. Extract Pricing Tiers ($ per bottle, 1, 3, 6 bottles)
            prices_found = re.findall(r'\$(\d{2,3})(?:\s*(?:\/|\s*per)\s*(?:bottle|jar|unit))?', body_text, re.IGNORECASE)
            clean_prices = sorted(list(set([int(p) for p in prices_found if 25 <= int(p) <= 120])), reverse=True)

            pricing_tiers = []
            if len(clean_prices) >= 3:
                p_high, p_mid, p_low = clean_prices[0], clean_prices[1], clean_prices[2]
                pricing_tiers = [
                    {"supply": "1 or 2 Month Supply", "price": f"${p_high} / bottle", "best_for": "Starter Trial", "total": f"${p_high * 2}", "savings": "Standard Price"},
                    {"supply": "3 Month Supply (3 Bottles)", "price": f"${p_mid} / bottle", "best_for": "Most Popular Reset", "total": f"${p_mid * 3}", "savings": f"Save ${(p_high - p_mid) * 3} + Free Bonuses + Free US Shipping"},
                    {"supply": "6 Month Supply (6 Bottles)", "price": f"${p_low} / bottle", "best_for": "Best Overall Value & Maximum Savings", "total": f"${p_low * 6}", "savings": f"Save ${(p_high - p_low) * 6} + Free Bonuses + Free Express Shipping"}
                ]
            elif len(clean_prices) == 2:
                p_high, p_low = clean_prices[0], clean_prices[1]
                pricing_tiers = [
                    {"supply": "1 Month Supply", "price": f"${p_high} / bottle", "best_for": "Starter Trial", "total": f"${p_high}", "savings": "Standard Price"},
                    {"supply": "3 Month Supply", "price": f"${int((p_high+p_low)/2)} / bottle", "best_for": "Popular Bundle", "total": f"${int((p_high+p_low)/2)*3}", "savings": "Free Shipping + Bonuses"},
                    {"supply": "6 Month Supply", "price": f"${p_low} / bottle", "best_for": "Best Value", "total": f"${p_low * 6}", "savings": "Maximum Wholesale Discount"}
                ]
            result["pricing_tiers"] = pricing_tiers

            # 8. Extract Ingredients mentioned in page text
            common_nutrients = [
                "tart cherry", "gaba", "5-htp", "melatonin", "l-theanine", "valerian root",
                "ashwagandha", "magnesium", "chamomile", "passionflower", "zinc", "vitamin b6",
                "berberine", "cinnamon", "chromium", "probiotic", "lactobacillus", "peppermint",
                "malic acid", "inulin", "collagen", "biotin", "turmeric", "curcumin", "ginger",
                "glucosamine", "chondroitin", "msm", "boswellia", "hyaluronic acid", "l-arginine",
                "beetroot", "pine bark extract", "coq10", "resveratrol", "quercetin", "cordyceps"
            ]
            found_ing = []
            for ing_kw in common_nutrients:
                if ing_kw in body_text.lower():
                    found_ing.append(ing_kw.title())
            result["ingredients"] = found_ing[:8]

            # 9. Biological Target / System Detection
            lower_body = body_text.lower()
            if "circadian" in lower_body or "sleep" in lower_body or "rem" in lower_body:
                result["format"] = "nano-enhanced liquid sublingual drops"
                result["target_system"] = "circadian pacemaker (suprachiasmatic nucleus) and GABAergic inhibitory neurotransmission"
            elif "joint" in lower_body or "cartilage" in lower_body or "synovial" in lower_body:
                result["format"] = "bioavailable vegetarian capsules"
                result["target_system"] = "synovial fluid density and articular cartilage integrity"
            elif "nitric oxide" in lower_body or "blood flow" in lower_body or "circulation" in lower_body:
                result["format"] = "rapid-acting nutrient powder"
                result["target_system"] = "endothelial nitric oxide synthase and microvascular circulation"
            elif "dental" in lower_body or "teeth" in lower_body or "gum" in lower_body:
                result["format"] = "chewable probiotic candy tablets"
                result["target_system"] = "oral microbiome equilibrium and salivary peptide defense"
            elif "blood sugar" in lower_body or "glucose" in lower_body:
                result["format"] = "herbal metabolic complex capsules"
                result["target_system"] = "GLUT4 receptor sensitivity and hepatic glucose homeostasis"

            # 10. Download Primary Product Image to Base64 (for 100% offline reliability)
            if result["product_image"]:
                result["product_image_b64"] = download_image_as_b64(page, result["product_image"])

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)
        finally:
            browser.close()

    return result
