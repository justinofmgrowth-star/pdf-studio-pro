import os
import io
import sys
import time
import zipfile
import subprocess
import pandas as pd
import streamlit as st
import importlib

# Auto-install Playwright chromium browser on Linux cloud if needed
if sys.platform.startswith("linux"):
    try:
        subprocess.run(["playwright", "install", "chromium"], check=False)
    except Exception:
        pass

import pdf_engine
importlib.reload(pdf_engine)
from pdf_engine import process_master_pdf_single_product, sanitize_filename, ANGLE_ARCHETYPES
from affiliate_scraper import scrape_affiliate_landing_page
from master_prompt_template import get_master_prompt
from pdf_uploader import auto_upload_pdf
from product_storage import (
    load_saved_products,
    save_or_update_product,
    delete_product,
    generate_title_recommendations
)

# Set page configuration
st.set_page_config(
    page_title="Clickable PDF Studio Pro",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
    }
    
    /* Main Layout Refinement */
    .block-container {
        padding-top: 1.8rem !important;
        padding-bottom: 3rem !important;
        max-width: 1250px !important;
    }
    
    /* Sleek Navigation Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #f1f5f9;
        padding: 5px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        border-radius: 8px;
        padding: 0 18px;
        font-weight: 600;
        font-size: 0.92rem;
        color: #475569;
        border: none !important;
        background: transparent;
        transition: all 0.15s ease;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06) !important;
    }
    
    /* Premium Buttons */
    .stButton>button {
        border-radius: 9px;
        font-weight: 600;
        letter-spacing: -0.01em;
        transition: all 0.2s ease;
    }
    button[kind="primary"] {
        background: linear-gradient(135deg, #1e40af 0%, #2563eb 100%) !important;
        border: none !important;
        color: #ffffff !important;
        padding: 0.65rem 1.6rem !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.28) !important;
    }
    button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.38) !important;
    }
    
    /* Clean Cards & Expanders */
    div[data-testid="stExpander"] {
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        background: #ffffff !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    }
    
    /* Modern Inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        border-radius: 8px !important;
        border: 1px solid #cbd5e1 !important;
        font-size: 0.93rem !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 2px rgba(37,99,235,0.15) !important;
    }
</style>
""", unsafe_allow_html=True)

# Define directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SAMPLE_CSV_PATH = os.path.join(BASE_DIR, "sample_products.csv")
LINKS_CSV_PATH = os.path.join(BASE_DIR, "uploaded_links.csv")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px; padding: 12px 14px; background: linear-gradient(135deg, #1e40af 0%, #2563eb 100%); border-radius: 12px; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);">
        <div style="width: 40px; height: 40px; background: #ffffff; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; box-shadow: 0 2px 6px rgba(0,0,0,0.12);">
            ⚡
        </div>
        <div>
            <div style="font-weight: 800; font-size: 14px; color: #ffffff; letter-spacing: -0.01em; line-height: 1.2;">PDF STUDIO</div>
            <div style="font-size: 9.5px; font-weight: 700; color: #93c5fd; letter-spacing: 0.08em; text-transform: uppercase;">PRO EDITION</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("##### ⚙️ Generator Settings")
    st.caption("1 Product • 1 Link • Multi-Angle PDFs")
    
    button_color = st.color_picker("Primary CTA Button Color:", value="#08796f")
    target_country = st.selectbox("Target Country:", ["GLOBAL", "USA", "UK", "CANADA", "AUSTRALIA"])
    target_audience = st.text_input("Target Audience:", value="Savvy Online Buyers & Enthusiasts")

    st.markdown("---")
    st.subheader("📂 Output Directory")
    st.caption(f"`{OUTPUT_DIR}`")
    if st.button("📁 Open Folder in Windows Explorer"):
        os.system(f'explorer "{OUTPUT_DIR}"')

# --- MAIN CONTENT ---
st.markdown("""
<div style="margin-bottom: 1.2rem; padding-bottom: 0.8rem; border-bottom: 1px solid #f1f5f9;">
    <div style="display: inline-flex; align-items: center; gap: 9px;">
        <span style="font-size: 1.85rem; font-weight: 800; color: #0f172a; letter-spacing: -0.02em;">🎯 Clickable PDF Studio Pro</span>
        <span style="background: #eff6ff; color: #2563eb; font-size: 0.72rem; font-weight: 700; padding: 3px 8px; border-radius: 20px; border: 1px solid #bfdbfe;">STUDIO EDITION</span>
    </div>
    <div style="font-size: 0.92rem; color: #64748b; margin-top: 3px;">
        Multi-Angle Clickable PDF Generator • Human-Written Style & Clean SERP Optimization
    </div>
</div>
""", unsafe_allow_html=True)

tab1, tab_library, tab_upload, tab_output = st.tabs([
    "🚀 PDF Generator",
    "📚 Product Library",
    "🌐 Auto-Uploader & Links",
    "📁 Output Files"
])

# ================= TAB 1: 1 PRODUCT MULTI-ANGLE =================
with tab1:
    saved_products = load_saved_products()
    preset_names = list(saved_products.keys())

    # --- SAVED PRODUCTS PRESET BAR ---
    st.markdown("""
    <div style="background: #f8fafc; border: 1.5px solid #cbd5e1; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px;">
        <strong style="color: #0f172a; font-size: 10pt;">📦 Saved Products Preset Library:</strong>
        <div style="font-size: 8.5pt; color: #64748b; margin-top: 2px;">
            Select a saved product preset to automatically populate all product details, keywords, and theme styling.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_pre1, col_pre2, col_pre3 = st.columns([2.5, 1, 0.5])
    preset_options = ["-- Select or Type New Product --"] + preset_names

    with col_pre1:
        if "selected_preset_name" not in st.session_state:
            st.session_state["selected_preset_name"] = "Yu Sleep" if "Yu Sleep" in saved_products else preset_options[0]

        curr_p_idx = preset_options.index(st.session_state["selected_preset_name"]) if st.session_state["selected_preset_name"] in preset_options else 0
        chosen_preset = st.selectbox(
            "Select Saved Product:",
            options=preset_options,
            index=curr_p_idx,
            help="Instantly populates all form fields upon selection."
        )

        # Handle preset switch
        if chosen_preset != st.session_state.get("last_loaded_preset"):
            st.session_state["last_loaded_preset"] = chosen_preset
            st.session_state["selected_preset_name"] = chosen_preset
            if chosen_preset in saved_products:
                sp = saved_products[chosen_preset]
                st.session_state["topic_input"] = sp.get("product_name", "")
                st.session_state["affiliate_input"] = sp.get("affiliate_url", "")
                st.session_state["keyword_input"] = sp.get("primary_keyword", "")
                st.session_state["secondary_input"] = sp.get("secondary_keywords", "")
                st.session_state["brand_input"] = sp.get("brand_name", "")
                st.session_state["theme_input"] = sp.get("theme_primary", "#047857")
                st.session_state["title_recs_variation"] = 0
                st.rerun()

    with col_pre2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("💾 Save Product", use_container_width=True):
            p_to_save = st.session_state.get("topic_input", "").strip()
            if p_to_save:
                save_or_update_product(
                    product_name=p_to_save,
                    affiliate_url=st.session_state.get("affiliate_input", ""),
                    primary_keyword=st.session_state.get("keyword_input", ""),
                    secondary_keywords=st.session_state.get("secondary_input", ""),
                    brand_name=st.session_state.get("brand_input", ""),
                    theme_primary=st.session_state.get("theme_input", "#047857")
                )
                st.session_state["selected_preset_name"] = p_to_save
                st.session_state["last_loaded_preset"] = p_to_save
                st.success(f"Saved '{p_to_save}'!")
                st.rerun()
            else:
                st.warning("Enter a Product Name first to save.")

    with col_pre3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if chosen_preset in saved_products:
            if st.button("🗑️", help="Delete this preset from library", use_container_width=True):
                delete_product(chosen_preset)
                st.session_state["selected_preset_name"] = "-- Select or Type New Product --"
                st.session_state["last_loaded_preset"] = "-- Select or Type New Product --"
                st.rerun()

    st.markdown("### 1. Product & Affiliate Details")

    # Initial session state seeds if empty
    if "topic_input" not in st.session_state:
        st.session_state["topic_input"] = ""
    if "affiliate_input" not in st.session_state:
        st.session_state["affiliate_input"] = ""
    if "keyword_input" not in st.session_state:
        st.session_state["keyword_input"] = ""
    if "secondary_input" not in st.session_state:
        st.session_state["secondary_input"] = ""
    if "brand_input" not in st.session_state:
        st.session_state["brand_input"] = ""
    if "theme_input" not in st.session_state:
        st.session_state["theme_input"] = "#1e40af"

    # Process pending preset load from Library BEFORE widgets are created
    if st.session_state.get("pending_preset_load"):
        p_loaded = st.session_state.pop("pending_preset_load")
        st.session_state["topic_input"] = p_loaded.get("product_name", "")
        st.session_state["affiliate_input"] = p_loaded.get("affiliate_url", "")
        st.session_state["keyword_input"] = p_loaded.get("primary_keyword", "")
        st.session_state["secondary_input"] = p_loaded.get("secondary_keywords", "")
        st.session_state["brand_input"] = p_loaded.get("brand_name", "")
        st.session_state["theme_input"] = p_loaded.get("theme_primary", "#047857")
        st.session_state["title_recs_variation"] = 0

    # Process pending autofetch request BEFORE widgets are created
    if st.session_state.get("pending_autofetch_url"):
        target_scrape_url = st.session_state.pop("pending_autofetch_url")
        with st.spinner("⚡ Analyzing product intelligence & synchronizing verified assets..."):
            res_scrape = scrape_affiliate_landing_page(target_scrape_url)
            if res_scrape.get("success"):
                st.session_state["scraped_data"] = res_scrape
                p_name = res_scrape.get("product_name") or ""
                b_name = res_scrape.get("brand_name") or ""
                if not p_name:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(target_scrape_url)
                    p_name = parsed.netloc.replace("www.", "").split(".")[0].title()
                if not b_name:
                    b_name = p_name.split()[0] if p_name else ""

                st.session_state["topic_input"] = p_name
                st.session_state["brand_input"] = b_name
                st.session_state["keyword_input"] = f"{p_name} Reviews 2026"
                st.session_state["affiliate_input"] = target_scrape_url
                if res_scrape.get("theme_primary"):
                    st.session_state["theme_input"] = res_scrape["theme_primary"]
                st.session_state["autofetch_alert"] = ("success", f"Successfully synchronized verified assets for '{p_name or target_scrape_url}'!")
            else:
                err_msg = res_scrape.get("error", "Could not fully parse")
                st.session_state["autofetch_alert"] = ("warning", f"Sync note: {err_msg}. High-authority verified fallbacks applied.")

    if "autofetch_alert" in st.session_state:
        alert_type, alert_msg = st.session_state.pop("autofetch_alert")
        if alert_type == "success":
            st.success(f"✅ {alert_msg}")
        else:
            st.warning(f"⚠️ {alert_msg}")

    # --- ROW 1: AFFILIATE URL & AUTO-SYNC ---
    if st.session_state.get("scraped_data"):
        col_url, col_sync, col_clr = st.columns([2.6, 1.0, 0.4])
    else:
        col_url, col_sync = st.columns([3.0, 1.0])

    with col_url:
        affiliate_url = st.text_input(
            "Affiliate / CTA URL *",
            key="affiliate_input",
            placeholder="https://amazon.com/... or your exact affiliate link"
        )
    with col_sync:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        sync_clicked = st.button("⚡ Auto-Sync Assets", type="primary", use_container_width=True)

    if st.session_state.get("scraped_data"):
        with col_clr:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🗑️", help="Clear scraped assets", use_container_width=True):
                st.session_state["scraped_data"] = None
                st.rerun()

    if sync_clicked:
        curr_aff_url = st.session_state.get("affiliate_input", affiliate_url)
        if not curr_aff_url or not curr_aff_url.strip().startswith("http"):
            st.error("⚠️ Please enter a valid Affiliate / CTA URL starting with http:// or https://")
        else:
            st.session_state["pending_autofetch_url"] = curr_aff_url.strip()
            st.rerun()

    # --- ROW 2: PRODUCT NAME & PRIMARY KEYWORD ---
    col_r1_left, col_r1_right = st.columns([1, 1])
    with col_r1_left:
        topic = st.text_input(
            "Product Name / Topic *",
            key="topic_input",
            placeholder="e.g. Sony WH-1000XM5, Yu Sleep, Joint Genesis"
        )
    with col_r1_right:
        keyword = st.text_input(
            "Primary Target Keyword *",
            key="keyword_input",
            placeholder="e.g. Yu Sleep Supplement Reviews"
        )

    # --- ROW 3: SECONDARY KEYWORDS & PRODUCT NICHE ---
    col_r2_left, col_r2_right = st.columns([1, 1])
    with col_r2_left:
        secondary_kw = st.text_input(
            "Secondary Keywords (Optional)",
            key="secondary_input",
            placeholder="e.g. reviews, ingredients, does it work, buy official"
        )
        brand = st.session_state.get("brand_input") or (topic.split()[0] if topic else "Verified Brand")

    with col_r2_right:
        category_choice = st.selectbox(
            "Product Niche / Category:",
            [
                "Auto-Detect (Smart Niche Detection)",
                "Health, Supplements & Wellness",
                "Tech, Electronics & Audio Gadgets",
                "Home, Ergonomics & Physical Goods",
                "Software, Digital Apps & Services"
            ],
            help="Content is naturally adapted to this category (e.g., ingredients & clinical evidence for wellness; specs & battery for tech)."
        )

    category_map = {
        "Auto-Detect (Smart Niche Detection)": "auto",
        "Health, Supplements & Wellness": "health_supplements",
        "Tech, Electronics & Audio Gadgets": "tech_gadgets",
        "Home, Ergonomics & Physical Goods": "lifestyle_goods",
        "Software, Digital Apps & Services": "digital_software"
    }
    selected_category = category_map.get(category_choice, "auto")

    # --- ROW 4: PDF TEMPLATE & ROTATION STRATEGY ---
    col_r3_left, col_r3_right = st.columns([1, 1])
    with col_r3_left:
        template_choice = st.selectbox(
            "PDF Visual Layout & Template:",
            [
                "🔥 Medical Reality Check (Vibrant Cards Style)",
                "🏛️ Authority Buying Guide (Classic Editorial Style)"
            ],
            index=0,
            help="Reality Check uses alternating vibrant accent cards & deal box. Authority Guide uses classic editorial typography."
        )
    with col_r3_right:
        rotation_choice = st.selectbox(
            "Template Rotation Across PDFs:",
            [
                "🎲 Rotate / Alternate Templates Automatically (Recommended)",
                "🔒 Use Selected Template for All PDFs"
            ],
            index=0,
            help="Alternating templates gives visual variety when generating multiple PDFs."
        )
        mix_templates = (rotation_choice == "🎲 Rotate / Alternate Templates Automatically (Recommended)")

    template_map = {
        "🔥 Medical Reality Check (Vibrant Cards Style)": "reality_check",
        "🏛️ Authority Buying Guide (Classic Editorial Style)": "joint_genesis"
    }
    selected_template = template_map.get(template_choice, "reality_check")

    # Website Brand Color Theme (Automatically extracted from official product website / presets)
    auto_theme_color = "#1e40af"
    if st.session_state.get("scraped_data"):
        detected_theme = st.session_state["scraped_data"].get("theme_primary")
        if detected_theme:
            auto_theme_color = detected_theme
    elif chosen_preset != "-- Select or Type New Product --" and chosen_preset in saved_products:
        preset_color = saved_products[chosen_preset].get("theme_primary")
        if preset_color:
            auto_theme_color = preset_color
    elif button_color:
        auto_theme_color = button_color

    if st.session_state.get("scraped_data"):
        sc = st.session_state["scraped_data"]
        with st.expander("✨ Scraped Affiliate Assets & Verified Bonus Details", expanded=True):
            col_sc1, col_sc2 = st.columns([1, 2.5])
            with col_sc1:
                sc_img = sc.get("product_image_b64") or sc.get("product_image")
                if sc_img:
                    st.image(sc_img, caption="Official Product Bottle/Package", use_container_width=True)
            with col_sc2:
                st.markdown(f"**Official Product Name:** `{sc.get('product_name')}`")
                st.markdown(f"**Guarantee:** `{sc.get('guarantee_days')}-Day Money-Back Guarantee`")
                if sc.get("ingredients"):
                    st.markdown(f"**Verified Active Ingredients:** {', '.join(sc.get('ingredients'))}")
                if sc.get("pricing_tiers"):
                    tiers_summary = " | ".join([f"{pt['supply']}: {pt['price']}" for pt in sc['pricing_tiers']])
                    st.markdown(f"**Pricing Tiers:** {tiers_summary}")
                if sc.get("bonuses"):
                    st.markdown(f"**🎁 Digital Bonuses Detected ({len(sc.get('bonuses'))}):**")
                    for b in sc.get("bonuses"):
                        b_has_img = "🖼️ with 3D cover art" if (b.get("image_b64") or b.get("image")) else ""
                        st.markdown(f"- **{b.get('title')}** ({b.get('value')}) {b_has_img}: {b.get('desc')[:110]}...")

    # Images accordion
    with st.expander("🖼️ Product Images (Upload from PC or Paste URLs)", expanded=False):
        col_up1, col_up2 = st.columns([1.5, 1])
        with col_up1:
            uploaded_product_img = st.file_uploader(
                "📁 Upload Product Image from PC (PNG, JPG, WEBP):",
                type=["png", "jpg", "jpeg", "webp"],
                help="Upload a high-resolution product image to feature on the PDF cover and review pages."
            )
        with col_up2:
            if uploaded_product_img is not None:
                st.image(uploaded_product_img, caption="✅ Uploaded Image Preview", width=130)

        img1_url_in = st.text_input(
            "🔗 Product Image URL (Optional):",
            value="",
            placeholder="https://example.com/product-bottle.png"
        )
        img2 = ""
        img3 = ""

        # Resolve primary image
        if uploaded_product_img is not None:
            import base64
            img_bytes = uploaded_product_img.read()
            mime_type = uploaded_product_img.type or "image/png"
            img1 = f"data:{mime_type};base64,{base64.b64encode(img_bytes).decode('utf-8')}"
        elif img1_url_in.strip():
            img1 = img1_url_in.strip()
        else:
            img1 = ""

    st.markdown("---")
    st.markdown("### 2. Select Quantity of Unique PDFs to Generate")

    pdf_quantity = st.number_input(
        "🔢 Number of Unique PDFs (Max 5):",
        min_value=1,
        max_value=5,
        value=5,
        step=1
    )

    # Generate Smart Title Recommendations based on product and keyword
    rec_var = st.session_state.get("title_recs_variation", 0)
    title_recommendations = generate_title_recommendations(topic, keyword, style_variation=rec_var)

    st.markdown("---")
    col_rec_hdr, col_rec_btn = st.columns([3, 1.2])
    with col_rec_hdr:
        st.markdown("### 📑 PDF Document Titles")
    with col_rec_btn:
        if st.button("🔄 Regenerate Titles", use_container_width=True):
            st.session_state["title_recs_variation"] = rec_var + 1
            st.rerun()

    custom_titles_list = []
    angle_labels = [
        "PDF #1 • Review Angle",
        "PDF #2 • Buyer's Guide",
        "PDF #3 • Pros & Cons",
        "PDF #4 • Comparisons",
        "PDF #5 • Value & Deals"
    ]

    for idx in range(pdf_quantity):
        rec_title = title_recommendations[idx % len(title_recommendations)]
        title_box = st.text_input(
            angle_labels[idx],
            value=rec_title,
            key=f"custom_title_angle_{idx}_{rec_var}_{topic}",
            help=f"Target headline for PDF #{idx+1}"
        )
        custom_titles_list.append(title_box.strip() or rec_title)

    pasted_text = st.text_area(
        "📝 Custom Editorial Notes (Optional - For PDF #1):",
        value="",
        placeholder="Optional: Enter custom review copy or product notes for PDF #1. If left blank, the system automatically writes high-converting multi-angle content.",
        height=75
    )

    st.markdown("""
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 18px; margin: 16px 0;">
        <strong style="color: #0f172a; font-size: 9.5pt;">🎯 Built-in Google SEO Optimization Active:</strong>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; font-size: 8.5pt; color: #475569;">
            <div>✔ <strong>SERP-Optimized Filenames:</strong> Clean hyphenated structure for Google URL ranking</div>
            <div>✔ <strong>Binary Metadata Injection:</strong> <code>/Title</code>, <code>/Subject</code>, & <code>/Keywords</code> embedded</div>
            <div>✔ <strong>Semantic Editorial Structure:</strong> H1, H2, comparison charts & trust badges</div>
            <div>✔ <strong>Anti-Spam Keyword Density:</strong> Natural human-written style targeting buyer intent</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button(f"⚡ Generate {pdf_quantity} High-Converting PDFs Now", type="primary", use_container_width=True):
        if not topic or not affiliate_url:
            st.error("Please enter Product Name and Affiliate URL!")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            generated_pdf_paths = []

            for i in range(pdf_quantity):
                angle_meta = ANGLE_ARCHETYPES[i % len(ANGLE_ARCHETYPES)]
                status_text.markdown(f"⏳ **Writing Unique PDF ({i+1}/{pdf_quantity}):** `{angle_meta['angle_name']}`...")

                # Determine template (alternate if mix_templates is checked)
                if mix_templates:
                    curr_template = "reality_check" if (i % 2 == 0) else "joint_genesis"
                else:
                    curr_template = selected_template

                try:
                    pdf_path = process_master_pdf_single_product(
                        keyword=keyword or topic,
                        affiliate_url=affiliate_url,
                        output_dir=OUTPUT_DIR,
                        topic=topic,
                        brand_name=brand,
                        angle_idx=i,
                        category=selected_category,
                        template=curr_template,
                        image_url_1=img1,
                        image_url_2=img2,
                        image_url_3=img3,
                        button_color=auto_theme_color or button_color,
                        pasted_text=pasted_text if (pasted_text.strip() and i == 0) else None,
                        scraped_data=st.session_state.get("scraped_data"),
                        custom_title=custom_titles_list[i],
                        secondary_keywords=secondary_kw,
                        theme_primary=auto_theme_color,
                        theme_accent=auto_theme_color
                    )
                    generated_pdf_paths.append(pdf_path)
                except Exception as e:
                    st.error(f"Error on PDF #{i+1}: {str(e)}")

                progress_bar.progress((i + 1) / pdf_quantity)
                time.sleep(0.3)

            status_text.markdown("✅ **All Unique PDFs Generated Successfully!**")
            st.success(f"Generated {len(generated_pdf_paths)} completely original SEO PDFs for '{topic}'!")

            # 1-Click ZIP Download for all PDFs
            if generated_pdf_paths:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for p in generated_pdf_paths:
                        zip_file.write(p, arcname=os.path.basename(p))
                zip_buffer.seek(0)
                
                safe_t = sanitize_filename(topic)
                st.download_button(
                    label=f"📦 Download All {len(generated_pdf_paths)} Unique PDFs as ZIP",
                    data=zip_buffer.getvalue(),
                    file_name=f"{safe_t}_Unique_SEO_PDFs_Bundle.zip",
                    mime="application/zip",
                    use_container_width=True
                )

# ================= TAB: PRODUCT LIBRARY =================
with tab_library:
    st.markdown("### 📚 Affiliate Product Library")
    st.caption("Store and manage your affiliate products, target URLs, and SEO keywords for quick 1-click access. Choose any saved preset in the Generator tab to instantly produce high-converting PDFs.")

    saved_prods = load_saved_products()

    # Form to add or edit product
    with st.expander("➕ Add New Product to Library", expanded=(len(saved_prods) == 0 or st.session_state.get("lib_edit_mode", False))):
        edit_target = st.session_state.get("lib_edit_target", {})
        
        col_lib1, col_lib2 = st.columns([1, 1])
        with col_lib1:
            lib_name = st.text_input(
                "Product Name *",
                value=edit_target.get("product_name", ""),
                placeholder="e.g. Yu Sleep, Joint Genesis, ProDentim",
                key="lib_form_name"
            )
            lib_keyword = st.text_input(
                "Primary Target Keyword *",
                value=edit_target.get("primary_keyword", ""),
                placeholder="e.g. Yu Sleep Supplement Reviews",
                key="lib_form_kw"
            )
            lib_brand = st.text_input(
                "Brand Name (Optional)",
                value=edit_target.get("brand_name", ""),
                placeholder="e.g. Yu, Biodynamix, Sony",
                key="lib_form_brand"
            )
            
        with col_lib2:
            lib_url = st.text_input(
                "Affiliate / CTA URL *",
                value=edit_target.get("affiliate_url", ""),
                placeholder="https://hop.clickbank.net/?affiliate=YOURID&vendor=example",
                key="lib_form_url"
            )
            lib_sec_kw = st.text_input(
                "Secondary Keywords (Comma separated)",
                value=edit_target.get("secondary_keywords", ""),
                placeholder="e.g. reviews, ingredients, does it work, buy official",
                key="lib_form_sec_kw"
            )
            col_th1, col_th2 = st.columns([1, 1])
            with col_th1:
                cat_options = [
                    "health_supplements",
                    "tech_gadgets",
                    "lifestyle_goods",
                    "digital_software",
                    "auto"
                ]
                cat_idx = cat_options.index(edit_target.get("category", "health_supplements")) if edit_target.get("category") in cat_options else 0
                lib_category = st.selectbox(
                    "Product Category:",
                    cat_options,
                    index=cat_idx,
                    key="lib_form_cat"
                )
            with col_th2:
                lib_theme = st.color_picker(
                    "Brand Color Theme:",
                    value=edit_target.get("theme_primary", "#047857"),
                    key="lib_form_color"
                )

        col_btn1, col_btn2 = st.columns([1.5, 3.5])
        with col_btn1:
            save_btn_label = "💾 Update Product" if edit_target else "💾 Save to Library"
            if st.button(save_btn_label, type="primary", use_container_width=True, key="lib_save_btn"):
                if not lib_name.strip() or not lib_url.strip() or not lib_keyword.strip():
                    st.error("⚠️ Product Name, Primary Keyword, and Affiliate URL are required!")
                else:
                    save_or_update_product(
                        product_name=lib_name.strip(),
                        affiliate_url=lib_url.strip(),
                        primary_keyword=lib_keyword.strip(),
                        secondary_keywords=lib_sec_kw.strip(),
                        brand_name=lib_brand.strip(),
                        category=lib_category,
                        theme_primary=lib_theme,
                        theme_accent=lib_theme
                    )
                    st.session_state["lib_edit_target"] = {}
                    st.session_state["lib_edit_mode"] = False
                    st.session_state["selected_preset_name"] = lib_name.strip()
                    st.session_state["last_loaded_preset"] = None
                    st.success(f"✅ '{lib_name.strip()}' successfully saved to Library!")
                    time.sleep(0.4)
                    st.rerun()
        with col_btn2:
            if edit_target:
                if st.button("Cancel Editing", key="lib_cancel_edit_btn"):
                    st.session_state["lib_edit_target"] = {}
                    st.session_state["lib_edit_mode"] = False
                    st.rerun()

    st.markdown("---")
    st.markdown(f"#### 📋 Saved Products in Your Library ({len(saved_prods)})")

    if not saved_prods:
        st.info("Your product library is currently empty. Use the form above to save your first product preset!")
    else:
        for p_name, p_data in saved_prods.items():
            t_color = p_data.get("theme_primary", "#1e40af")
            with st.container():
                st.markdown(f"""
                <div style="background: #ffffff; border: 1.5px solid {t_color}; border-left: 6px solid {t_color}; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.04);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 1.15rem; font-weight: 800; color: {t_color};">🏷️ {p_name}</span>
                        <span style="background: {t_color}18; color: {t_color}; font-size: 8pt; font-weight: 700; padding: 3px 8px; border-radius: 4px;">{p_data.get('category', 'health_supplements').replace('_', ' ').title()}</span>
                    </div>
                    <div style="font-size: 8.8pt; color: #334155; margin-bottom: 4px;">
                        <strong>🎯 Primary Keyword:</strong> <code>{p_data.get('primary_keyword')}</code>
                    </div>
                    <div style="font-size: 8.5pt; color: #475569; margin-bottom: 4px;">
                        <strong>🔗 Affiliate Link:</strong> <a href="{p_data.get('affiliate_url')}" target="_blank" style="color: {t_color}; word-break: break-all;">{p_data.get('affiliate_url')[:65]}...</a>
                    </div>
                    <div style="font-size: 8.2pt; color: #64748b;">
                        <strong>🔑 Secondary Keywords:</strong> {p_data.get('secondary_keywords') or 'None'}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                col_act1, col_act2, col_act3, _ = st.columns([1.6, 1, 1, 2.5])
                with col_act1:
                    if st.button(f"🚀 Use in Generator", key=f"use_lib_{p_name}", use_container_width=True):
                        st.session_state["selected_preset_name"] = p_name
                        st.session_state["last_loaded_preset"] = None
                        st.session_state["pending_preset_load"] = p_data
                        st.toast(f"✅ Loaded '{p_name}' into Generator!")
                        st.rerun()
                with col_act2:
                    if st.button(f"✏️ Edit", key=f"edit_lib_{p_name}", use_container_width=True):
                        st.session_state["lib_edit_target"] = p_data
                        st.session_state["lib_edit_mode"] = True
                        st.rerun()
                with col_act3:
                    if st.button(f"🗑️ Delete", key=f"del_lib_{p_name}", use_container_width=True):
                        delete_product(p_name)
                        if st.session_state.get("selected_preset_name") == p_name:
                            st.session_state["selected_preset_name"] = "-- Select or Type New Product --"
                            st.session_state["last_loaded_preset"] = None
                        st.rerun()

# ================= TAB: AUTO-UPLOADER & LIVE LINKS =================
with tab_upload:
    st.markdown("### 🌐 Batch PDF Uploader & Live Links Extractor")
    st.caption("Upload multiple PDFs to generate live, shareable public links automatically.")

    pdf_files_avail = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".pdf")]

    engine_preset = st.selectbox(
        "⚡ Select Upload Destination / Hosting Engine:",
        [
            "🚀 Catbox.moe (Instant Permanent Direct Public PDF Link - Recommended)",
            "⚡ Temp.sh (High-Speed Public Document Host)",
            "🌐 Custom Web Pages / Forms (Enter URLs below)"
        ],
        help="Catbox and Temp.sh provide 100% guaranteed, instant, permanent public URLs that Google SERP indexes."
    )

    col_u1, col_u2 = st.columns([1.6, 1])

    with col_u1:
        if "Custom" in engine_preset:
            target_web_urls_raw = st.text_area(
                "Target Website Upload URLs (One URL per line) *",
                value="https://catbox.moe",
                placeholder="https://site1.com/upload\nhttps://site2.com/upload\nhttps://site3.com/upload",
                height=110,
                help="Enter target website submission URLs (one URL per line)."
            )
        elif "Catbox" in engine_preset:
            target_web_urls_raw = "https://catbox.moe"
            st.info("⚡ **Direct Cloud Engine Active:** PDFs will be uploaded to Catbox.moe for instant, permanent, direct public URLs.")
        else:
            target_web_urls_raw = "https://temp.sh"
            st.info("⚡ **Direct Cloud Engine Active:** PDFs will be uploaded to Temp.sh for high-speed public document hosting.")

        col_p1, col_p2 = st.columns([1, 2])
        with col_p1:
            select_all_pdfs = st.checkbox("✅ Select All PDFs", value=False)
        with col_p2:
            default_selection = pdf_files_avail if select_all_pdfs else ([pdf_files_avail[0]] if pdf_files_avail else [])
            selected_pdfs_to_upload = st.multiselect(
                "Select PDFs from Output Folder to Upload *",
                options=pdf_files_avail,
                default=default_selection,
                help="Select one or more generated PDFs to upload."
            )

    with col_u2:
        watch_upload = st.checkbox("👁️ Watch Browser during Upload", value=False, help="Display live browser window during custom website uploads.")
        
        # Parsed URL list
        urls_list = [u.strip() for u in target_web_urls_raw.strip().split("\n") if u.strip().startswith("http")]

        if len(urls_list) > 1 and len(selected_pdfs_to_upload) > 1:
            upload_mode = st.radio(
                "Upload Distribution Strategy:",
                ["Distribute 1 PDF per Website (Sequential)", "Upload Every Selected PDF to Every Website (Matrix)"]
            )
        else:
            upload_mode = "Standard"

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 Start Batch Upload & Extract Live Links", type="primary", use_container_width=True):
            if not urls_list or not selected_pdfs_to_upload:
                st.error("Please enter at least 1 valid Target Website URL and select at least 1 PDF!")
            else:
                # Build upload task pairs (url, pdf_file)
                tasks = []
                if "Matrix" in upload_mode:
                    for u in urls_list:
                        for pdf in selected_pdfs_to_upload:
                            tasks.append((u, pdf))
                else:
                    # Sequential 1-to-1 or spread
                    for i, pdf in enumerate(selected_pdfs_to_upload):
                        target_u = urls_list[i % len(urls_list)]
                        tasks.append((target_u, pdf))

                prog_bar = st.progress(0)
                status_lbl = st.empty()
                success_count = 0

                for idx, (t_url, t_pdf) in enumerate(tasks):
                    status_lbl.markdown(f"⏳ **Uploading ({idx+1}/{len(tasks)}):** `{t_pdf}` to `{t_url}`...")
                    full_pdf_p = os.path.join(OUTPUT_DIR, t_pdf)

                    try:
                        res = auto_upload_pdf(
                            target_page_url=t_url,
                            pdf_file_path=full_pdf_p,
                            show_browser=watch_upload
                        )
                        success_count += 1
                        st.toast(f"Uploaded: {t_pdf} ✅")
                    except Exception as ex:
                        st.error(f"Error on {t_pdf} -> {t_url}: {str(ex)}")

                    prog_bar.progress((idx + 1) / len(tasks))
                    time.sleep(0.5)

                status_lbl.markdown("✅ **Batch Upload Process Completed!**")
                st.success(f"Successfully processed {success_count} / {len(tasks)} uploads!")
                time.sleep(0.5)
                st.rerun()

    st.markdown("---")
    
    # --- TRACKER SECTION WITH DELETE CAPABILITIES ---
    col_head1, col_head2 = st.columns([3, 1])
    with col_head1:
        st.subheader("📋 Uploaded PDFs Live Tracker")
        st.caption("All successfully uploaded PDFs with their live public verification links.")
    with col_head2:
        links_df = get_uploaded_links()
        if not links_df.empty:
            if st.button("🗑️ Clear All Tracker Records", use_container_width=True):
                clear_all_uploaded_links()
                st.toast("All upload records cleared! 🗑️")
                time.sleep(0.3)
                st.rerun()

    if links_df.empty:
        st.info("No PDFs uploaded yet. Enter URLs and select PDFs above to upload!")
    else:
        st.markdown(f"**Total Tracked Uploads:** `{len(links_df)}`")
        
        # Display each row with an individual Delete button
        for row_i, row in links_df.iterrows():
            col_t_time, col_t_pdf, col_t_site, col_t_link, col_t_del = st.columns([1.3, 2.2, 2.2, 2, 0.8])
            
            with col_t_time:
                st.caption(f"🕒 {row.get('timestamp', '')}")
            with col_t_pdf:
                st.markdown(f"📄 **{row.get('pdf_name', '')}**")
            with col_t_site:
                st.caption(f"🌐 {row.get('target_website', '')[:35]}...")
            with col_t_link:
                l_url = row.get('live_url', '#')
                st.markdown(f"[🔗 Open Live PDF]({l_url})")
            with col_t_del:
                if st.button("🗑️", key=f"del_link_{row_i}", help="Delete this record from tracker"):
                    delete_uploaded_link(row_i)
                    st.toast("Record deleted! 🗑️")
                    time.sleep(0.2)
                    st.rerun()
            st.divider()

# ================= TAB: OUTPUT LIBRARY =================
with tab_output:
    st.markdown("### 📁 Generated PDFs Library")

    pdf_files = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".pdf")]

    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 2])
    with col_btn1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    with col_btn2:
        if st.button("📂 Open Output Folder", use_container_width=True):
            os.system(f'explorer "{OUTPUT_DIR}"')
    with col_btn3:
        if pdf_files:
            if st.button("🗑️ Delete All PDFs", type="secondary", use_container_width=True):
                for pf in pdf_files:
                    try:
                        os.remove(os.path.join(OUTPUT_DIR, pf))
                    except Exception:
                        pass
                st.toast("All generated PDFs deleted from output folder! 🗑️")
                time.sleep(0.3)
                st.rerun()
                time.sleep(0.3)
                st.rerun()

    if not pdf_files:
        st.info("No PDFs found in output directory.")
    else:
        st.markdown(f"**Total PDFs:** `{len(pdf_files)}`")
        for pdf_file in reversed(pdf_files):
            full_path = os.path.join(OUTPUT_DIR, pdf_file)
            if not os.path.exists(full_path):
                continue
            size_kb = os.path.getsize(full_path) // 1024
            mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(full_path)))

            col_a, col_b, col_c = st.columns([5, 1.2, 1.2])
            with col_a:
                st.markdown(f"📄 **{pdf_file}** &bull; `{size_kb} KB` &bull; *{mtime}*")
            with col_b:
                with open(full_path, "rb") as pf:
                    st.download_button(
                        label="⬇️ Download",
                        data=pf.read(),
                        file_name=pdf_file,
                        mime="application/pdf",
                        key=f"dl_{pdf_file}",
                        use_container_width=True
                    )
            with col_c:
                if st.button("🗑️ Delete", key=f"del_{pdf_file}", use_container_width=True):
                    try:
                        os.remove(full_path)
                        st.toast(f"Deleted from laptop: {pdf_file} 🗑️")
                        time.sleep(0.3)
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error deleting: {ex}")
            st.divider()
