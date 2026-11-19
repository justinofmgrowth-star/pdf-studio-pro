# 🚀 AI Affiliate & SEO Clickable PDF Generator

Ek powerful aur aasan desktop web app jo **DeepSeek AI** aur **Headless Chromium** ka use karke **SEO-friendly, High-Converting Clickable PDFs** banati hai.

---

## 🌟 Khaas Khususiyat (Features)
- **100% Clickable PDFs:**
  - Product image clickable hai (affiliate link par open hoti hai).
  - High-converting CTA buttons ("Check Price on Amazon", "Get Deal", etc.).
  - Clickable Table of Contents (jump between Overview, Features, Pros & Cons, Verdict).
- **SEO & Copywriting with DeepSeek AI:**
  - Catchy title, executive summary, specs, pros & cons, and final score.
- **Bulk PDF Generation:**
  - Single product mode (instant test).
  - Bulk CSV / Excel upload (ek click me 50+ PDFs ready).
- **No-Code Friendly:**
  - Aapko kisi code ya terminal ki zaroorat nahi hai. Bas `Start_App.bat` par double-click karein!

---

## 🏃‍♂️ Kaise Chalayein (How to Run)

1. Is folder me **`Start_App.bat`** file par double click karein.
2. Kuch seconds me aapka browser khul jayega aur samne Dashboard aa jayega:
   - **URL:** `http://localhost:8501`
3. Sidebar me apna **DeepSeek API Key** enter karein (agar key nahi hai to Test Mode me bhi click karke sample PDFs bana sakte hain).
4. **Single Product** tab me details daal kar ya **Bulk CSV** upload karke **"Generate"** button dabayein.
5. Saari PDFs `output/` folder me save ho jayengi!

---

## 📁 File Structure
- `Start_App.bat` -> App chalane ke liye 1-click launcher.
- `app.py` -> Streamlit user-friendly UI dashboard.
- `pdf_engine.py` -> Chromium Playwright & DeepSeek conversion engine.
- `sample_products.csv` -> Bulk upload ke liye example template.
- `output/` -> Jahan aapki sabhi generated PDFs save hoti hain.
