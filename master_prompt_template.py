def get_master_prompt(
    keyword: str,
    affiliate_url: str,
    topic: str = "",
    brand_name: str = "",
    secondary_keywords: str = "",
    target_country: str = "GLOBAL / USA",
    target_audience: str = "Savvy Consumers & Online Buyers",
    cta_urls: str = ""
) -> str:
    """
    Returns the exact Master Prompt formatted with the user's inputs.
    """
    topic_str = topic or keyword
    brand_str = brand_name or "Verified Brand"
    cta_str = cta_urls or affiliate_url

    prompt = f"""PROFESSIONAL SEO ARTICLE + CLICKABLE PDF MASTER PROMPT

Act as a Professional SEO Content Writer, SEO Strategist, Technical Copywriter, Editor, and Premium PDF Designer.

Create a complete, original, human-readable, Google-friendly SEO article and convert it into a beautiful, professionally designed, clickable PDF.

━━━━━━━━━━━━━━━━━━━━━━
INPUT
━━━━━━━━━━━━━━━━━━━━━━

Primary Keyword: {keyword}
Secondary Keywords: {secondary_keywords or f"{keyword} review, best {keyword}, buy {keyword} online, {keyword} price and deals, top rated {keyword}"}
Affiliate URLs: {affiliate_url}
CTA URLs: {cta_str}
Brand/Website: {brand_str}
Target Country: {target_country}
Target Audience: {target_audience}
Topic: {topic_str}
Optional Services/Brands: {brand_str}

━━━━━━━━━━━━━━━━━━━━━━
ARTICLE REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━

Write approximately 2,500 words.

Write for real readers first and SEO second.

Use:
• Natural semantic SEO
• Search intent optimization
• E-E-A-T principles
• Clear, trustworthy explanations
• Short readable paragraphs
• Active voice
• Useful original analysis
• Natural keyword variations

Avoid:
• Keyword stuffing
• AI-style filler
• Repetitive sentences
• Fake statistics
• Fake reviews
• Unsupported claims
• Excessive promotional language
• Guaranteed ranking claims

━━━━━━━━━━━━━━━━━━━━━━
TOP OF PDF — IMPORTANT
━━━━━━━━━━━━━━━━━━━━━━

DO NOT display labels such as:
"SEO TITLE"
"META DESCRIPTION"
"SEO-FRIENDLY URL"
"SEO TITLE:"
"URL:"

The PDF must look like a professionally published article.

At the top of the article, display:
1. THE ACTUAL ARTICLE TITLE
   - Large, bold, professional H1
   - Primary keyword naturally included
   - Strong but not clickbait

2. META DESCRIPTION
   - Place directly below the article title
   - 140–160 characters
   - Natural and useful
   - No "Meta Description:" label

3. Then START THE ARTICLE.

━━━━━━━━━━━━━━━━━━━━━━
ARTICLE STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━

Use exactly ONE H1.
Then use logical: H2, H3, H4

Include where relevant:
• Strong introduction
• Table of Contents (Clickable anchors)
• Topic explanation
• Important features
• Benefits
• Limitations
• Pricing/value
• Compatibility
• Performance
• Security/privacy
• Legality/safety where relevant
• Comparison table when useful
• Pros & Cons (4–7 Pros, 3–6 Cons)
• Expert/practical tips
• Common mistakes
• 6–10 FAQs
• Conclusion

━━━━━━━━━━━━━━━━━━━━━━
FIRST CTA — VERY IMPORTANT
━━━━━━━━━━━━━━━━━━━━━━

The FIRST CTA button MUST appear immediately after the meta description and BEFORE the main article introduction.
It must be:
• Center aligned
• Professionally designed
• Clickable: <a href="{affiliate_url}" target="_blank" rel="nofollow sponsored noopener" class="cta-button">Check Official Details</a>
• High contrast, rounded corners, subtle shadow

━━━━━━━━━━━━━━━━━━━━━━
CTA STRATEGY
━━━━━━━━━━━━━━━━━━━━━━

Spread 5–11 clickable affiliate links naturally across sections using varied text:
"Check Official Details", "Explore This Service", "View Current Options", "See Official Pricing", "Learn More", "Check Availability".
ONLY use the supplied affiliate URL: {affiliate_url}

━━━━━━━━━━━━━━━━━━━━━━
AFFILIATE DISCLOSURE
━━━━━━━━━━━━━━━━━━━━━━

DO NOT include any affiliate disclosure, sponsorship notice, or commission disclaimer anywhere in the article. Keep the document completely editorial, authoritative, and clean.

━━━━━━━━━━━━━━━━━━━━━━
IMAGES
━━━━━━━━━━━━━━━━━━━━━━

Up to 3 relevant images:
Image 1: After introduction
Image 2: Around main features/comparison
Image 3: Near final decision

━━━━━━━━━━━━━━━━━━━━━━
FINAL SEARCH KEYWORDS PAGE
━━━━━━━━━━━━━━━━━━━━━━

After the article, create a separate final page titled:
"Search Keywords"
Add 20–25 highly relevant primary, long-tail, and commercial keywords.
"""
    return prompt
