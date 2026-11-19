import os
import time
import json
import re
from urllib.parse import urljoin, urlparse
import requests
import pandas as pd
from typing import Dict, Any, Optional, List
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LINKS_CSV_PATH = os.path.join(BASE_DIR, "uploaded_links.csv")

def save_uploaded_link(pdf_name: str, target_url: str, live_url: str, status: str = "Active ✅"):
    """Saves uploaded PDF details to a persistent CSV tracker."""
    new_record = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        "pdf_name": pdf_name,
        "target_website": target_url,
        "live_url": live_url,
        "status": status
    }
    
    if os.path.exists(LINKS_CSV_PATH):
        try:
            df = pd.read_csv(LINKS_CSV_PATH)
            df = pd.concat([pd.DataFrame([new_record]), df], ignore_index=True)
        except Exception:
            df = pd.DataFrame([new_record])
    else:
        df = pd.DataFrame([new_record])
        
    df.to_csv(LINKS_CSV_PATH, index=False)

def get_uploaded_links() -> pd.DataFrame:
    """Returns all tracked uploaded links as a DataFrame."""
    if os.path.exists(LINKS_CSV_PATH):
        try:
            return pd.read_csv(LINKS_CSV_PATH)
        except Exception:
            pass
    return pd.DataFrame(columns=["timestamp", "pdf_name", "target_website", "live_url", "status"])

def delete_uploaded_link(row_idx: int):
    """Deletes a specific tracked link by index from uploaded_links.csv."""
    if os.path.exists(LINKS_CSV_PATH):
        try:
            df = pd.read_csv(LINKS_CSV_PATH)
            if 0 <= row_idx < len(df):
                df = df.drop(df.index[row_idx]).reset_index(drop=True)
                df.to_csv(LINKS_CSV_PATH, index=False)
        except Exception:
            pass

def clear_all_uploaded_links():
    """Wipes all tracked upload records."""
    if os.path.exists(LINKS_CSV_PATH):
        try:
            os.remove(LINKS_CSV_PATH)
        except Exception:
            pass

def upload_via_catbox_engine(pdf_file_path: str) -> Optional[str]:
    """Uploads directly to Catbox.moe for a 100% permanent, public, high-speed direct link."""
    try:
        pdf_name = os.path.basename(pdf_file_path)
        with open(pdf_file_path, "rb") as f:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (pdf_name, f, "application/pdf")},
                timeout=40
            )
            if r.status_code == 200 and r.text.strip().startswith("http"):
                return r.text.strip()
    except Exception as e:
        print(f"[Catbox Upload Error] {e}")
    return None

def upload_via_tempsh_engine(pdf_file_path: str) -> Optional[str]:
    """Uploads directly to Temp.sh for a fast, publicly accessible direct link."""
    try:
        pdf_name = os.path.basename(pdf_file_path)
        with open(pdf_file_path, "rb") as f:
            r = requests.post(
                "https://temp.sh/upload",
                files={"file": (pdf_name, f, "application/pdf")},
                timeout=40
            )
            if r.status_code == 200 and r.text.strip().startswith("http"):
                return r.text.strip()
    except Exception as e:
        print(f"[Temp.sh Upload Error] {e}")
    return None

def verify_link_is_active(url: str, timeout: int = 8) -> bool:
    """
    Actively checks whether a URL returns HTTP 200 and points to a real accessible resource.
    Prevents saving broken 404/403 URLs or soft 404 error pages.
    """
    if not url or not url.startswith("http"):
        return False
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True)
        if r.status_code == 200:
            ct = (r.headers.get("content-type") or "").lower()
            if any(term in ct for term in ["pdf", "octet-stream", "document", "download"]):
                return True
            # Inspect initial bytes of HTML responses to detect soft 404s
            if "html" in ct:
                chunk = next(r.iter_content(1024), b"").decode("utf-8", errors="ignore").lower()
                if any(err_term in chunk for err_term in ["404 not found", "page not found", "chttpexception", "requested url was not found", "error 404"]):
                    return False
            return True
    except Exception:
        pass
    return False

def scan_and_rank_file_inputs(page) -> List[Any]:
    """
    Intelligently reads the page DOM to discover all file upload inputs.
    Scores and ranks them so PDF/Document uploaders are prioritized over image-only inputs.
    """
    try:
        all_inputs = page.locator("input[type='file']").all()
    except Exception:
        return []

    if not all_inputs:
        return []

    scored_inputs = []
    for idx, inp in enumerate(all_inputs):
        score = 10
        try:
            accept = (inp.get_attribute("accept") or "").lower()
            name = (inp.get_attribute("name") or "").lower()
            inp_id = (inp.get_attribute("id") or "").lower()

            # 1. Inspect Accept Attribute
            if accept:
                if "pdf" in accept or "application/pdf" in accept or "*/*" in accept or ".*" in accept or "octet-stream" in accept:
                    score += 60
                elif any(img in accept for img in ["image/", ".jpg", ".png", ".gif", ".jpeg", "image/*"]):
                    score -= 50

            # 2. Inspect Name / ID keywords
            for kw in ["doc", "pdf", "file", "attach", "upload", "qqfile"]:
                if kw in name or kw in inp_id:
                    score += 20
            for kw in ["img", "image", "photo", "avatar", "picture", "logo"]:
                if kw in name or kw in inp_id:
                    score -= 30

            # 3. Inspect Form Group & Parent Container Text (Bootstrap, Tailwind, Custom Forms)
            try:
                group_text = inp.evaluate(
                    """el => {
                        let formGroup = el.closest('.form-group, .row, div[class*="group"], tr, fieldset, form');
                        let curr = el;
                        let ancestor_chain = '';
                        while (curr && curr !== document.body) {
                            if (curr.id) ancestor_chain += ' ' + curr.id;
                            if (curr.className && typeof curr.className === 'string') ancestor_chain += ' ' + curr.className;
                            curr = curr.parentElement;
                        }
                        let inner = formGroup ? formGroup.innerText : '';
                        return (ancestor_chain + ' ' + inner).toLowerCase();
                    }"""
                )
                if any(w in group_text for w in ["pdf", "document", "docx", "attachment", "attachments", "attach", "files", "cv", "resume"]):
                    score += 80
                if any(w in group_text for w in ["logo", "avatar", "photo", "image", "jpg", "png", "headshot"]):
                    score -= 60
            except Exception:
                pass

        except Exception:
            pass

        scored_inputs.append((score, idx, inp))

    # Sort descending by score
    scored_inputs.sort(key=lambda x: x[0], reverse=True)
    return [item[2] for item in scored_inputs]

def auto_upload_pdf(
    target_page_url: str,
    pdf_file_path: str,
    show_browser: bool = False,
    timeout_sec: int = 60
) -> Dict[str, Any]:
    """
    Automates uploading a PDF to any target web page.
    1. Scans DOM for PDF-specific upload inputs (FineUploader, Dropzone, Webforms).
    2. Intercepts network payloads (XHR/Fetch) & page source for live file URLs.
    3. Transparent: NEVER silently routes custom URLs to third-party hosts like Catbox.
    """
    if not os.path.exists(pdf_file_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_file_path}")

    abs_pdf_path = os.path.abspath(pdf_file_path)
    pdf_filename = os.path.basename(abs_pdf_path)
    url_lower = target_page_url.lower()

    # Fast Direct APIs when explicitly targeted
    if "catbox" in url_lower:
        cat_url = upload_via_catbox_engine(abs_pdf_path)
        if cat_url:
            save_uploaded_link(pdf_filename, "Catbox.moe (Direct API)", cat_url)
            return {"success": True, "pdf_name": pdf_filename, "target_url": target_page_url, "live_url": cat_url, "timestamp": time.strftime("%Y-%m-%d %H:%M")}

    if "temp.sh" in url_lower:
        tsh_url = upload_via_tempsh_engine(abs_pdf_path)
        if tsh_url:
            save_uploaded_link(pdf_filename, "Temp.sh (Direct API)", tsh_url)
            return {"success": True, "pdf_name": pdf_filename, "target_url": target_page_url, "live_url": tsh_url, "timestamp": time.strftime("%Y-%m-%d %H:%M")}

    # Advanced Chromium Engine for Custom Websites
    captured_urls: List[str] = []
    ajax_upload_payloads: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not show_browser,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Listen to Network Responses (Deep Payload & JSON Inspect)
        def handle_response(response):
            try:
                ct = response.headers.get("content-type", "").lower()
                resp_url = response.url

                # JSON Responses (AJAX upload handlers, FineUploader, Dropzone, API endpoints)
                if "json" in ct:
                    try:
                        j_data = response.json()
                        ajax_upload_payloads.append(j_data)

                        def extract_urls(obj):
                            if isinstance(obj, dict):
                                # FineUploader or generic upload handlers
                                if obj.get("success") is True:
                                    u_name = obj.get("uploadName") or obj.get("name") or pdf_filename
                                    uuid_val = obj.get("uuid") or obj.get("id")
                                    if u_name:
                                        captured_urls.append(urljoin(target_page_url, f"/uploads/{u_name}"))
                                        captured_urls.append(urljoin(target_page_url, f"/uploads/files/{u_name}"))
                                    if uuid_val and u_name:
                                        captured_urls.append(urljoin(target_page_url, f"/uploads/{uuid_val}/{u_name}"))

                                for k, v in obj.items():
                                    if any(term in k.lower() for term in ["url", "link", "download", "file", "path", "src", "href"]):
                                        if isinstance(v, str):
                                            full_u = urljoin(target_page_url, v)
                                            if full_u.startswith("http") and full_u not in captured_urls:
                                                captured_urls.append(full_u)
                                    extract_urls(v)
                            elif isinstance(obj, list):
                                for item in obj:
                                    extract_urls(item)

                        extract_urls(j_data)
                    except Exception:
                        pass

                # HTML / Text Responses
                elif "text" in ct or "html" in ct or "plain" in ct:
                    try:
                        text = response.text()
                        # Extract PDF or file upload links
                        matches = re.findall(
                            r'(?:href|src|url)=[\'"]?([^\'"\s<>]+\.(?:pdf|docx|zip)|[^\'"\s<>]+/(?:uploads|files|webform)/[^\'"\s<>]+)[\'"]?',
                            text,
                            re.IGNORECASE
                        )
                        for m in matches:
                            full_u = urljoin(target_page_url, m)
                            if full_u.startswith("http") and full_u not in captured_urls:
                                captured_urls.append(full_u)
                    except Exception:
                        pass
            except Exception:
                pass

        page.on("response", handle_response)

        # 1. Navigate to target URL
        page.goto(target_page_url, wait_until="domcontentloaded", timeout=40000)
        time.sleep(2)

        # 2. Accept cookies / terms checkboxes if present
        try:
            for cb in page.locator("input[type='checkbox']").all()[:3]:
                if not cb.is_checked():
                    cb.check(timeout=500)
        except Exception:
            pass

        # 3. Smart DOM Scan: Locate and prioritize the correct PDF upload input
        ranked_inputs = scan_and_rank_file_inputs(page)
        has_file_input = False
        chosen_file_input = None

        for f_inp in ranked_inputs:
            try:
                f_inp.set_input_files(abs_pdf_path)
                has_file_input = True
                chosen_file_input = f_inp
                break
            except Exception:
                continue

        # 4. If direct file inputs were hidden or custom, trigger file chooser via button/dropzone
        if not has_file_input:
            upload_triggers = [
                ".qq-upload-button-selector",
                ".qq-upload-button",
                "div[class*='qq-upload']",
                "div[class*='dropzone']",
                "div[class*='upload']",
                "button:has-text('Upload')",
                "button:has-text('Choose File')",
                "button:has-text('Select File')",
                "button:has-text('Browse')",
                "label[for*='file']",
                "a:has-text('Upload')"
            ]
            for trigger in upload_triggers:
                try:
                    loc = page.locator(trigger).first
                    if loc.is_visible(timeout=1000):
                        with page.expect_file_chooser(timeout=2500) as fc_info:
                            loc.click()
                        file_chooser = fc_info.value
                        file_chooser.set_files(abs_pdf_path)
                        has_file_input = True
                        chosen_file_input = loc
                        break
                except Exception:
                    continue

        if not has_file_input:
            browser.close()
            raise RuntimeError(f"Could not locate an active PDF upload form or file input on {target_page_url}.")

        # Allow AJAX uploader to process file
        time.sleep(3)

        # Identify specific target form container to avoid header search forms
        target_form = None
        if chosen_file_input:
            try:
                tf = chosen_file_input.locator("xpath=ancestor::form")
                if tf.count() > 0:
                    target_form = tf.first
            except Exception:
                pass

        # 5. Auto-populate standard form fields if present (titles, emails, reviewer info)
        try:
            scope = target_form if target_form else page
            for txt_input in scope.locator("input[type='text'], input[type='email'], input[type='url'], textarea").all():
                if txt_input.is_visible() and not txt_input.input_value():
                    field_name = (txt_input.get_attribute("name") or "").lower()
                    field_id = (txt_input.get_attribute("id") or "").lower()
                    field_cls = (txt_input.get_attribute("class") or "").lower()

                    # Strictly ignore search bars
                    if field_name in ["q", "s", "search", "query"] or "search" in field_cls or "search" in field_id:
                        continue

                    if "email" in field_name or "email" in field_id:
                        txt_input.fill("editorial.reviews@gmail.com")
                    elif "deadline" in field_name or "date" in field_name:
                        txt_input.fill("2026-12-31 23:59:59")
                    elif "url" in field_name or "website" in field_id:
                        txt_input.fill("https://reviews.hub/report")
                    elif "title" in field_name or "position" in field_name or "subject" in field_id:
                        txt_input.fill("Product Evaluation & Safety Analysis 2026")
                    elif "name" in field_name:
                        txt_input.fill("Editorial Reviewer")
                    else:
                        txt_input.fill("Editorial Review")
        except Exception:
            pass

        # 6. Check for Anti-Spam / Cloudflare Turnstile / Captcha
        has_turnstile = page.locator(".cf-turnstile, iframe[src*='challenges.cloudflare.com'], #turnstile-token, [name='cf-turnstile-response']").count() > 0
        if has_turnstile and show_browser:
            # In live visible browser mode, give up to 15 seconds for turnstile check to pass
            for _ in range(15):
                try:
                    passed = page.evaluate("() => window.turnstilePassed === true || (document.getElementById('turnstile-token') && document.getElementById('turnstile-token').value.length > 5)")
                    if passed:
                        break
                except Exception:
                    pass
                time.sleep(1)

        # 7. Attempt form submission inside target form
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit')",
            "button:has-text('Send')",
            "button:has-text('Publish')",
            "button:has-text('Post')",
            "button:has-text('Upload')",
            "button:has-text('Start Upload')"
        ]
        submit_scope = target_form if target_form else page
        for sub_sel in submit_selectors:
            try:
                sub_btn = submit_scope.locator(sub_sel).first
                if sub_btn.is_visible(timeout=800):
                    btn_text = (sub_btn.inner_text() or "").lower()
                    if "search" in btn_text or "find" in btn_text:
                        continue
                    sub_btn.click()
                    break
            except Exception:
                pass

        # 8. Deep Network & DOM Inspect Extraction (Poll up to 20 seconds)
        # Uses strict filename matching and live HTTP 200 ping verification
        base_stem = os.path.splitext(pdf_filename)[0].lower()
        clean_stem = re.sub(r'[^a-zA-Z0-9]', '', base_stem)
        live_link = None
        start_wait = time.time()

        while time.time() - start_wait < 20:
            # Check A: Network-captured URLs (Exact matches verified with live HTTP ping)
            if captured_urls:
                for u in reversed(captured_urls):
                    u_lower = u.lower()
                    u_clean = re.sub(r'[^a-zA-Z0-9]', '', u_lower)
                    if base_stem in u_lower or clean_stem in u_clean or pdf_filename.lower() in u_lower:
                        if verify_link_is_active(u):
                            live_link = u
                            break
            if live_link:
                break

            # Check B: DOM Links (Strictly matched to uploaded PDF filename, verified with live ping)
            try:
                dom_links = page.locator("a[href*='.pdf'], a[href*='download'], a[href*='/files/'], a[href*='/uploads/'], a[href*='webform']").all()
                for a in dom_links:
                    href = a.get_attribute("href")
                    if href and href != "#" and href != target_page_url:
                        href_lower = href.lower()
                        href_clean = re.sub(r'[^a-zA-Z0-9]', '', href_lower)
                        anchor_text = (a.inner_text() or "").lower()
                        # Strict match: must belong to our uploaded file, ignore site privacy policies/terms
                        if base_stem in href_lower or clean_stem in href_clean or base_stem in anchor_text:
                            full_href = urljoin(target_page_url, href)
                            if full_href.startswith("http") and "search" not in full_href.lower():
                                if verify_link_is_active(full_href):
                                    live_link = full_href
                                    break
            except Exception:
                pass
            if live_link:
                break

            # Check C: Readonly Inputs, Textareas, or Clipboard Copy buttons
            try:
                for inp in page.locator("input[readonly], input[value*='http'], textarea").all():
                    val = (inp.get_attribute("value") or inp.input_value() or "").strip()
                    if val.startswith("http") and any(term in val.lower() for term in ["download", "file", "view", ".pdf", "upload"]):
                        if verify_link_is_active(val):
                            live_link = val
                            break
            except Exception:
                pass
            if live_link:
                break

            # Check D: Hidden form inputs updated by AJAX upload callbacks (e.g. FineUploader, Dropzone)
            try:
                hidden_scope = target_form if target_form else page
                for h_name in ["attachname", "attachid", "imgfilename", "file_name", "uploaded_file", "attach"]:
                    matched_inputs = hidden_scope.locator(f"input[name*='{h_name}' i], input[id*='{h_name}' i]").all()
                    for h_el in matched_inputs:
                        h_val = (h_el.get_attribute("value") or "").strip()
                        if h_val:
                            h_clean = re.sub(r'[^a-zA-Z0-9]', '', h_val.lower())
                            if base_stem in h_val.lower() or clean_stem in h_clean or h_val.lower().endswith(".pdf"):
                                # Test candidate paths with live HTTP verification
                                for cand_path in [f"/uploads/files/{h_val}", f"/uploads/{h_val}", f"/{h_val}"]:
                                    cand_url = urljoin(target_page_url, cand_path)
                                    if verify_link_is_active(cand_url):
                                        live_link = cand_url
                                        break
                        if live_link:
                            break
                    if live_link:
                        break
            except Exception:
                pass
            if live_link:
                break

            time.sleep(1)

        # Check E: Page Redirection (e.g. view page after successful submission, ignore search queries)
        if not live_link and page.url != target_page_url:
            p_url_lower = page.url.lower()
            if "search" not in p_url_lower and "add" not in p_url_lower and "q=" not in p_url_lower:
                if verify_link_is_active(page.url):
                    live_link = page.url

        browser.close()

        # 9. Handle Result Transparently (NO fake 404s, NO unverified links)
        if not live_link and ajax_upload_payloads:
            for p_item in ajax_upload_payloads:
                if isinstance(p_item, dict) and p_item.get("success") is True:
                    u_name = p_item.get("uploadName") or p_item.get("name")
                    if u_name:
                        for test_p in [f"/uploads/files/{u_name}", f"/uploads/{u_name}"]:
                            test_cand = urljoin(target_page_url, test_p)
                            if verify_link_is_active(test_cand):
                                live_link = test_cand
                                break
                if live_link:
                    break

        if not live_link:
            raise RuntimeError(
                f"File was uploaded to {target_page_url}, but the website holds submissions in private moderation or did not publish an accessible public link. No dead or 404 URL was saved."
            )

        # Save to persistent tracker (Only 100% verified HTTP 200 links reach here)
        save_uploaded_link(pdf_filename, target_page_url, live_link)

        return {
            "success": True,
            "pdf_name": pdf_filename,
            "target_url": target_page_url,
            "live_url": live_link,
            "timestamp": time.strftime("%Y-%m-%d %H:%M")
        }
