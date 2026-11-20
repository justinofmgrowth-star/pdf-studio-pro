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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
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

def scrape_affiliate_landing_page(url: str, timeout_ms: int = 35000) -> Dict[str, Any]:
    """
    Deep-scans the affiliate URL with full-page smooth scrolling to trigger all lazy-loaded
    assets, dynamic bonuses, ingredient panels, pricing tiers, and brand color styling.
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
        "cta_color": "#f59e0b",
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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 950}
        )
        page = context.new_page()

        try:
            # 1. Navigate & follow all redirects to final landing page
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass
            time.sleep(2.0)

            final_url = page.url
            result["final_url"] = final_url

            # 2. Smooth Full-Page Auto-Scroll to trigger all lazy images & bonus sections
            try:
                page.evaluate("""async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 750;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            if (totalHeight >= scrollHeight || totalHeight > 32000) {
                                clearInterval(timer);
                                window.scrollTo(0, 0); // Return to top for hero analysis
                                resolve();
                            }
                        }, 80);
                    });
                }""")
                time.sleep(1.0)
            except Exception:
                pass

            # 3. Force resolve all lazy image attributes (data-src, data-lazy, srcset)
            try:
                page.evaluate("""() => {
                    document.querySelectorAll('img').forEach(img => {
                        const lazySrc = img.getAttribute('data-src') || 
                                        img.getAttribute('data-lazy-src') || 
                                        img.getAttribute('data-original') || 
                                        img.getAttribute('lazy-src') ||
                                        (img.getAttribute('srcset') ? img.getAttribute('srcset').split(' ')[0] : '');
                        if (lazySrc && (!img.src || img.src.includes('data:image') || img.src.includes('placeholder') || img.src.includes('blank'))) {
                            img.src = lazySrc;
                        }
                    });
                }""")
            except Exception:
                pass

            # 4. Extract Document Title & Meta Information
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
            h1_text = meta_info.get("h1", "")

            # Clean product name candidate
            raw_name = og_title or doc_title or h1_text
            clean_name = re.sub(
                r'[-–|:•]\s*(?:text\s*presentation|video\s*presentation|presentation|vsl|video\s*sales\s*letter|official\s*(?:website|site|store|page|portal)?|reviews?|store|shop|get|order|discount|buy\s*now|buy\s*online|supplement|formula|special\s*offer|special\s*discount).*$',
                '',
                raw_name,
                flags=re.IGNORECASE
            ).strip()
            clean_name = re.sub(r'\b(?:text|video)\s*presentation\b', '', clean_name, flags=re.IGNORECASE).strip()
            if not clean_name or len(clean_name) > 35:
                if h1_text and len(h1_text) < 35:
                    clean_name = re.sub(r'[-–|:•]\s*(?:text\s*presentation|video\s*presentation|presentation|vsl|official).*$', '', h1_text, flags=re.IGNORECASE).strip()
            
            result["product_name"] = clean_name or raw_name[:30].strip()
            result["headline"] = og_title or doc_title or h1_text

            # 5. Extract Sales Page Visual Palette (Exact Brand Colors & CTA Styling)
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

                    // Extract CTA Button Color
                    let ctaColor = '';
                    const ctaSelectors = [
                        'a[href*="pay"]', 'a[href*="order"]', 'a[href*="checkout"]', 'a[href*="cart"]',
                        '.btn-order', '.btn-buy', '.btn-checkout', '.order-btn', '.cta-btn', '.add-to-cart',
                        'button[type="submit"]', '.button-primary', '.btn-primary', '.vsl-btn'
                    ];
                    for (const sel of ctaSelectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const st = window.getComputedStyle(el);
                            const bg = parseColor(st.backgroundColor);
                            if (bg && bg !== '#ffffff' && bg !== '#000000') {
                                ctaColor = bg;
                                break;
                            }
                        }
                    }

                    // Extract Primary Brand Theme
                    let primaryColor = '';
                    const brandSelectors = ['header', '.header', 'nav', '.navbar', '.hero', '.banner', 'h1', '.logo-area'];
                    for (const sel of brandSelectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const st = window.getComputedStyle(el);
                            const bg = parseColor(st.backgroundColor);
                            if (bg && bg !== '#ffffff' && bg !== '#000000' && bg !== '#f8fafc' && bg !== '#f1f5f9') {
                                primaryColor = bg;
                                break;
                            }
                        }
                    }

                    // Extract Accent Highlight (Badges, Seals, Cards)
                    let accentColor = '';
                    const badge = document.querySelector('.badge, .seal, .guarantee, .highlight, .featured');
                    if (badge) {
                        const bSt = window.getComputedStyle(badge);
                        const bBg = parseColor(bSt.backgroundColor);
                        if (bBg && bBg !== '#ffffff' && bBg !== '#000000') {
                            accentColor = bBg;
                        }
                    }

                    return {
                        primary: primaryColor || '#1e40af',
                        accent: accentColor || '#2563eb',
                        cta: ctaColor || '#f59e0b'
                    };
                }""")
                if theme_colors:
                    if theme_colors.get("primary"):
                        result["theme_primary"] = theme_colors["primary"]
                    if theme_colors.get("accent"):
                        result["theme_accent"] = theme_colors["accent"]
                    if theme_colors.get("cta"):
                        result["cta_color"] = theme_colors["cta"]
            except Exception:
                pass

            # 6. Extract Full Page Text for Analysis
            body_text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
            result["raw_text_sample"] = body_text[:3000]

            # 7. Guarantee Days Extraction (e.g. 60-day, 90-day, 180-day)
            guarantee_match = re.search(r'(\d{2,3})\s*[- ]?(?:day|days)\s*(?:money[- ]back|guarantee|risk[- ]free)', body_text, re.IGNORECASE)
            if guarantee_match:
                result["guarantee_days"] = int(guarantee_match.group(1))

            # 8. Deep Image Extraction & Scoring (Hero Bottle, Packages & Badges)
            image_candidates = page.evaluate("""() => {
                const results = [];
                const seen = new Set();
                
                document.querySelectorAll('img').forEach(img => {
                    let src = img.currentSrc || img.src || '';
                    const lazySrc = img.getAttribute('data-src') || 
                                    img.getAttribute('data-lazy-src') || 
                                    img.getAttribute('data-original') || 
                                    (img.getAttribute('srcset') ? img.getAttribute('srcset').split(' ')[0] : '');
                    if (lazySrc && (lazySrc.startsWith('http') || lazySrc.startsWith('/'))) {
                        src = lazySrc;
                    }
                    if (!src || src.startsWith('data:image/svg') || seen.has(src)) return;
                    seen.add(src);
                    
                    const rect = img.getBoundingClientRect();
                    const parentText = ((img.closest('div, section, li, article')?.innerText) || '').toLowerCase();
                    const parentClass = ((img.closest('div, section, li, article')?.className) || '').toLowerCase();
                    
                    results.push({
                        src: src,
                        alt: img.alt || '',
                        className: img.className || '',
                        width: rect.width || img.naturalWidth || 0,
                        height: rect.height || img.naturalHeight || 0,
                        parentContext: parentText.slice(0, 300) + ' ' + parentClass
                    });
                });
                return results;
            }""")

            scored_product_imgs = []
            for img in image_candidates:
                try:
                    src = img.get("src", "")
                    alt = img.get("alt", "")
                    width = img.get("width", 0)
                    height = img.get("height", 0)

                    if width < 100 or height < 100:
                        continue

                    lower_src = src.lower()
                    lower_alt = alt.lower()

                    # Filter out payment icons, badges, social icons
                    skip_keywords = ["visa", "mastercard", "paypal", "amex", "stripe", "arrow", "stars", "fda-badge", "footer", "favicon"]
                    if any(sk in lower_src or sk in lower_alt for sk in skip_keywords):
                        continue

                    score = 0
                    # Positive keyword hints for main product bottle/box
                    product_hints = ["bottle", "product", "pack", "bundle", "jar", "supplement", "box", "hero", "dropper", "container", "supply", "front"]
                    for ph in product_hints:
                        if ph in lower_src:
                            score += 18
                        if ph in lower_alt:
                            score += 22

                    if clean_name.lower() in lower_src or clean_name.lower() in lower_alt:
                        score += 40

                    # Favor high-res images
                    score += int(min(width, 700) / 20)
                    score += int(min(height, 700) / 20)

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
            sec_imgs = [img[1] for img in scored_product_imgs[1:5]]
            result["secondary_images"] = sec_imgs

            # 9. UNLIMITED DYNAMIC BONUS EXTRACTOR (Bonus #1, #2, #3, #4, #5, #6...)
            # A. DOM Structured Bonus Extraction (highest fidelity for cards/boxes)
            dom_bonuses = page.evaluate("""() => {
                const results = [];
                const seenNums = new Set();
                const headings = Array.from(document.querySelectorAll('h2, h3, h4, h5, strong, b, .bonus-title, .bonus-name'));
                
                for (const h of headings) {
                    const text = (h.innerText || '').trim();
                    const m = text.match(/(?:Free\s+Bonus|Bonus)\s*#?\s*(\d+)[\s:–-]*(.*)/i);
                    if (m) {
                        const num = parseInt(m[1]);
                        if (seenNums.has(num)) continue;
                        
                        let title = m[2] ? m[2].trim() : '';
                        const card = h.closest('div[class*="bonus"], .card, .box, section, .col, .row') || h.parentElement;
                        let desc = '';
                        let val = '$59.00';
                        let imgSrc = '';
                        
                        if (card) {
                            const cardText = card.innerText || '';
                            const vMatch = cardText.match(/(?:Retail\s*Value|Value|RRP|\$)\s*:?\s*\$?(\d{2,3})/i);
                            if (vMatch) val = '$' + vMatch[1];
                            
                            const ps = Array.from(card.querySelectorAll('p, div'));
                            for (const p of ps) {
                                const pText = (p.innerText || '').trim();
                                if (pText.length > 25 && !pText.toLowerCase().includes('bonus #') && !pText.toLowerCase().includes('value:')) {
                                    desc = pText;
                                    break;
                                }
                            }
                            
                            const img = card.querySelector('img');
                            if (img) {
                                imgSrc = img.currentSrc || img.src || img.getAttribute('data-src') || img.getAttribute('data-lazy-src') || '';
                            }
                        }
                        
                        seenNums.add(num);
                        results.push({ num: num, title: title, desc: desc, value: val, imgSrc: imgSrc });
                    }
                }
                return results;
            }""")

            # B. Body Text Regex Extraction for any bonuses not caught in DOM cards
            regex_bonuses = {}
            bonus_matches = re.finditer(
                r'(?:Free\s+Bonus|Bonus)\s*#?\s*(\d+)[\s:–-]+([^\n\r]+)(?:[\r\n]+(?:\(Retail\s*Value|\$|Instant|RRP|Value|\(RRP)[^\n\r]*)?(?:[\r\n]+([^\n\r]{15,350}))?',
                body_text,
                re.IGNORECASE
            )
            for bm in bonus_matches:
                b_num = int(bm.group(1))
                b_title = bm.group(2).strip()
                b_title = re.sub(r'\(.*?\)', '', b_title).strip(' -:–')
                b_desc = bm.group(3).strip() if len(bm.groups()) >= 3 and bm.group(3) else ""
                if 1 <= b_num <= 10 and b_num not in regex_bonuses and len(b_title) > 3:
                    regex_bonuses[b_num] = {
                        "num": b_num,
                        "title": b_title,
                        "desc": b_desc,
                        "value": "$59.00"
                    }

            # Merge all bonuses in order (1, 2, 3, 4, 5...)
            merged_bonuses = {}
            for db in dom_bonuses:
                n = db.get("num", 1)
                merged_bonuses[n] = db

            for n, rb in regex_bonuses.items():
                if n not in merged_bonuses:
                    merged_bonuses[n] = rb
                else:
                    if not merged_bonuses[n].get("desc") and rb.get("desc"):
                        merged_bonuses[n]["desc"] = rb["desc"]
                    if not merged_bonuses[n].get("title") and rb.get("title"):
                        merged_bonuses[n]["title"] = rb["title"]

            # Match bonus cover images from image candidates
            bonus_images_pool = []
            for img in image_candidates:
                isrc = img.get("src", "")
                ialt = img.get("alt", "").lower()
                pctx = img.get("parentContext", "").lower()
                if any(k in isrc.lower() or k in ialt or k in pctx for k in ["bonus", "book", "ebook", "guide", "gift", "report", "cover"]):
                    bonus_images_pool.append(isrc)

            final_bonuses = []
            for b_num in sorted(merged_bonuses.keys()):
                b_data = merged_bonuses[b_num]
                b_title = b_data.get("title") or f"Special VIP Guide {b_num}"
                b_desc = b_data.get("desc") or f"Step-by-step master digital blueprint detailing proven protocols to maximize formula efficacy and long-term results."
                b_val = b_data.get("value") or "$59.00"

                # Match image: card image or pool image or keyword image
                b_img = b_data.get("imgSrc", "")
                if not b_img or b_img.startswith("data:image/svg"):
                    for candidate_img in bonus_images_pool:
                        cand_lower = candidate_img.lower()
                        if f"bonus{b_num}" in cand_lower or f"bonus-{b_num}" in cand_lower or f"bonus_{b_num}" in cand_lower:
                            b_img = candidate_img
                            break
                    if not b_img and (b_num - 1) < len(bonus_images_pool):
                        b_img = bonus_images_pool[b_num - 1]

                b_b64 = download_image_as_b64(page, b_img) if b_img else ""

                final_bonuses.append({
                    "title": f"Bonus #{b_num}: {b_title}",
                    "value": b_val,
                    "desc": b_desc,
                    "image": b_img,
                    "image_b64": b_b64
                })

            result["bonuses"] = final_bonuses

            # 10. Extract Exact Pricing Tiers ($ per bottle, 1, 3, 6 bottles)
            prices_found = re.findall(r'\$(\d{2,3})(?:\s*(?:\/|\s*per)\s*(?:bottle|jar|unit))?', body_text, re.IGNORECASE)
            clean_prices = sorted(list(set([int(p) for p in prices_found if 25 <= int(p) <= 120])), reverse=True)

            bonus_count_str = f"{len(final_bonuses)} Free VIP Bonuses" if len(final_bonuses) > 0 else "Free VIP Bonuses"
            pricing_tiers = []
            if len(clean_prices) >= 3:
                p_high, p_mid, p_low = clean_prices[0], clean_prices[1], clean_prices[2]
                pricing_tiers = [
                    {"supply": "1 or 2 Month Supply", "price": f"${p_high} / bottle", "best_for": "Starter Trial", "total": f"${p_high * 2}", "savings": "Standard Price"},
                    {"supply": "3 Month Supply (3 Bottles)", "price": f"${p_mid} / bottle", "best_for": "Most Popular Reset", "total": f"${p_mid * 3}", "savings": f"Save ${(p_high - p_mid) * 3} + {bonus_count_str} + Free US Shipping"},
                    {"supply": "6 Month Supply (6 Bottles)", "price": f"${p_low} / bottle", "best_for": "Best Overall Value & Maximum Savings", "total": f"${p_low * 6}", "savings": f"Save ${(p_high - p_low) * 6} + {bonus_count_str} + Free Express Shipping"}
                ]
            elif len(clean_prices) == 2:
                p_high, p_low = clean_prices[0], clean_prices[1]
                pricing_tiers = [
                    {"supply": "1 Month Supply", "price": f"${p_high} / bottle", "best_for": "Starter Trial", "total": f"${p_high}", "savings": "Standard Price"},
                    {"supply": "3 Month Supply", "price": f"${int((p_high+p_low)/2)} / bottle", "best_for": "Popular Bundle", "total": f"${int((p_high+p_low)/2)*3}", "savings": f"Free Shipping + {bonus_count_str}"},
                    {"supply": "6 Month Supply", "price": f"${p_low} / bottle", "best_for": "Best Value", "total": f"${p_low * 6}", "savings": "Maximum Wholesale Discount"}
                ]
            result["pricing_tiers"] = pricing_tiers

            # 11. Extract Ingredients mentioned across the full page text
            common_nutrients = [
                "tart cherry", "gaba", "5-htp", "melatonin", "l-theanine", "valerian root",
                "ashwagandha", "magnesium", "chamomile", "passionflower", "zinc", "vitamin b6",
                "berberine", "cinnamon", "chromium", "probiotic", "lactobacillus", "peppermint",
                "malic acid", "inulin", "collagen", "biotin", "turmeric", "curcumin", "ginger",
                "glucosamine", "chondroitin", "msm", "boswellia", "hyaluronic acid", "l-arginine",
                "beetroot", "pine bark extract", "coq10", "resveratrol", "quercetin", "cordyceps",
                "spirulina", "chlorella", "elderberry", "echinacea", "vitamin c", "vitamin d3",
                "vitamin k2", "maca root", "fenugreek", "saw palmetto", "milk thistle", "alpha lipoic acid"
            ]
            found_ing = []
            for ing_kw in common_nutrients:
                if ing_kw in body_text.lower():
                    found_ing.append(ing_kw.title())
            result["ingredients"] = found_ing[:10]

            # 12. Biological Target & Category Detection
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
            elif "dental" in lower_body or "teeth" in lower_body or "gum" in lower_body or "oral" in lower_body:
                result["format"] = "chewable probiotic candy tablets"
                result["target_system"] = "oral microbiome equilibrium and salivary peptide defense"
            elif "blood sugar" in lower_body or "glucose" in lower_body:
                result["format"] = "herbal metabolic complex capsules"
                result["target_system"] = "GLUT4 receptor sensitivity and hepatic glucose homeostasis"

            # 13. Download Primary High-Res Product Image to Base64
            if result["product_image"]:
                result["product_image_b64"] = download_image_as_b64(page, result["product_image"])

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)
        finally:
            browser.close()

    return result
