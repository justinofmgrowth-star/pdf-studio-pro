@echo off
title AI Affiliate and SEO Clickable PDF Generator
cd /d "C:\Users\ADMIN\.gemini\antigravity\scratch\affiliate_pdf_generator"

:: Permanent Shields against bytecode cache and stale modules
set PYTHONDONTWRITEBYTECODE=1
set PYTHONUNBUFFERED=1
if exist "__pycache__" rmdir /s /q "__pycache__" >nul 2>&1

echo ====================================================================
echo         AI AFFILIATE AND SEO CLICKABLE PDF GENERATOR
echo ====================================================================
echo.
echo Launching App Dashboard in your browser...
echo.

start "" "http://localhost:8501"
.venv\Scripts\streamlit.exe run app.py --server.port=8501 --server.headless=true --browser.gatherUsageStats=false

pause
