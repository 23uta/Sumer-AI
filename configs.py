from google import genai

apikey="YOUR_GEMINI_API_KEY"
client = genai.Client(api_key=apikey) 

locallinks = {
    # 🚖 التوصيل والطعام والتاكسي
    "baly"                          : "https://baly.iq",
    "talabat"                       : "https://iraq.talabat.com",
    "alsaree3"                      : "https://alsaree3.com",
    "toters"                        : "https://totersapp.com",
    "lezzoo"                        : "https://www.lezzoo.com",
    "talabatey"                     : "https://talabatey.com",
    "tiptop"                        : "https://tiptopiq.com",

    # 🎓 الجامعات ومؤسسات التعليم
    "baghdad university"            : "https://www.uobaghdad.edu.iq",
    "university of baghdad"         : "https://www.uobaghdad.edu.iq",
    "mustansiriyah university"      : "https://uomustansiriyah.edu.iq",
    "mustansiriya university"       : "https://uomustansiriyah.edu.iq",
    "technology university"         : "https://uotechnology.edu.iq",
    "university of technology"      : "https://uotechnology.edu.iq",
    "nahrain university"            : "https://www.nahrainuniv.edu.iq",
    "al-nahrain university"         : "https://www.nahrainuniv.edu.iq",
    "basra university"              : "https://www.uobasrah.edu.iq",
    "university of basra"           : "https://www.uobasrah.edu.iq",
    "mosul university"              : "https://www.uomosul.edu.iq",
    "university of mosul"           : "https://www.uomosul.edu.iq",
    "kufa university"               : "https://uokufa.edu.iq",
    "university of kufa"            : "https://uokufa.edu.iq",
    "kerbala university"            : "https://www.uokerbala.edu.iq",
    "university of karbala"         : "https://www.uokerbala.edu.iq",
    "babylon university"            : "https://www.uobabylon.edu.iq",
    "university of babylon"         : "https://www.uobabylon.edu.iq",
    "tikrit university"             : "https://tu.edu.iq",
    "university of tikrit"          : "https://tu.edu.iq",
    "diyala university"             : "https://www.uodiyala.edu.iq",
    "university of diyala"          : "https://www.uodiyala.edu.iq",
    "anbar university"              : "https://www.uoanbar.edu.iq",
    "university of anbar"           : "https://www.uoanbar.edu.iq",

    # 🏛️ وزارات وبوابات حكومية وخدمية
    "ur portal"                     : "https://ur.gov.iq",
    "ur electronic portal"          : "https://ur.gov.iq",
    "ministry of education"         : "https://www.moedu.gov.iq",
    "ministry of health"            : "https://moh.gov.iq",
    "ministry of finance"           : "https://www.mof.gov.iq",
    "ministry of higher education"  : "https://mohesr.gov.iq",
    "iraqi civil status"            : "https://nid-moi.gov.iq",
    "national card reservation"     : "https://nid-moi.gov.iq",
    "parliament"                    : "https://www.parliament.iq",
    "iraqi parliament"              : "https://www.parliament.iq",

    # 🏦 بنوك ومصارف وخدمات مالية
    "rafidain bank"                 : "https://www.rafidain-bank.gov.iq",
    "rasheed bank"                  : "https://www.rasheedbank.gov.iq",
    "trade bank iraq"               : "https://www.tbi.iq",
    "tbi"                           : "https://www.tbi.iq",
    "central bank of iraq"          : "https://cbi.iq",
    "cbi"                           : "https://cbi.iq",
    "zain cash"                     : "https://www.zaincash.iq",
    "zain cash login"               : "https://www.zaincash.iq/portal/login",
    "qi card"                       : "https://www.qicard.com",
    "super qi"                      : "https://www.qicard.com",
    "asia hawala"                   : "https://asiahawala.com",
    "fib"                           : "https://fib.iq",
    "first iraqi bank"              : "https://fib.iq",
    "fastpay"                       : "https://www.fast-pay.cash",
    "switch bypass"                 : "https://switch.com.iq",

    # 📦 شحن ولوجستيك دولي ومحلي
    "dhl iraq"                      : "https://www.dhl.com/iq-en/home.html",
    "fedex iraq"                    : "https://www.fedex.com/en-iq/home.html",
    "aramex iraq"                   : "https://www.aramex.com/iq/en",
    "sandooq"                       : "https://sandooq.xyz",

    # 🛒 تسوق ومتاجر إلكترونية
    "miswag"                        : "https://miswag.com",
    "uredi"                         : "https://uredi.iq",
    "baghdadi sooq"                 : "https://baghdadisooq.com",
    "shaway"                        : "https://shaway.iq",
    "tamata"                        : "https://tamata.com",
    "opensooq iraq"                 : "https://iq.opensooq.com",
    "opensooq"                      : "https://iq.opensooq.com",

    # 📰 وكالات إخبارية عراقية
    "alsumaria"                     : "https://www.alsumaria.tv",
    "rudaw"                         : "https://www.rudaw.net",
    "shafaq"                        : "https://shafaq.com",
    "shafaq news"                   : "https://shafaq.com",
    "mawazin"                       : "https://mawazin.net",

    # 📱 شركات الاتصالات والإنترنت
    "zain iraq"                     : "https://www.iq.zain.com",
    "zain"                          : "https://www.iq.zain.com",
    "asiacell"                      : "https://www.asiacell.com",
    "korek"                         : "https://www.korek.com",
    "korek telecom"                 : "https://www.korek.com",
}

report_prompt = """You are an expert Document Structurer and JSON Generator. Your sole task is to analyze user requests, research data, or essays, and convert them into a structured JSON payload that maps directly to our custom Python `python-docx` builder functions.

### CRITICAL RULES (STRICTLY ENFORCED):
1. OUTPUT FORMAT: Respond ONLY with a valid, clean JSON object inside a single Markdown code block. Do NOT include any conversational introduction, explanation, or notes.
2. NO NULL VALUES: Never use "null" or None for any HEX color fields or parameters. If a color is not specified by the user, ALWAYS default to a solid fallback value (e.g., "FFFFFF" for page_color, "1F3964" for borders, "2E75B6" for text colors).
3. FULL STRUCTURE: Every key must have a concrete string, integer, float, or boolean value. Do NOT omit required sub-keys like "color", "size", or "style" inside the "border" or "page_setup" blocks.
4. ENCODING: Support full UTF-8 for Arabic and English text based on user requirements.

### THE PREDEFINED BLOCK SCHEMA:
Your output JSON must follow this exact structure, ensuring NO field resolves to null:

{
  "page_setup": {
    "size": "A4",
    "top_margin": 1.0,
    "bottom_margin": 1.0,
    "left_margin": 1.25,
    "right_margin": 1.25,
    "orientation": "portrait",
    "page_color": "FFFFFF", 
    "border": {"color": "1F3964", "size": 4, "style": "single"}
  },
  "header_footer": {
    "header": {"text": "Academic Report", "logo_path": "logo.png"},
    "footer": {"text": "Confidential"},
    "include_page_number": true
  },
  "cover_page": {
    "has_cover": true,
    "title": "string",
    "subtitle": "string",
    "author": "string",
    "date": "string",
    "department": "string"
  },
  "report_structure": [
    { "type": "toc", "data": { "title": "الفهرس" } },
    { "type": "page_break" },
    { "type": "section_break", "data": { "break_type": "next_page" } },
    { "type": "horizontal_rule", "data": { "color": "2E75B6", "size": 6 } },
    { "type": "heading1", "data": "string" },
    { "type": "heading2", "data": "string" },
    { "type": "heading3", "data": "string" },
    { "type": "paragraph", "data": { "text": "string", "align": "right" } },
    { "type": "rich_text", "data": { "text": "string", "bold": true, "italic": false, "underline": false, "size": 12 } },
    { "type": "colored_text", "data": { "text": "string", "color": "2E75B6", "highlight": "YELLOW" } },
    { "type": "text_box", "data": { "text": "string", "bg_color": "EBF3FB", "border_color": "2E75B6" } },
    { "type": "bullet_list", "data": ["item1", "item2"] },
    { "type": "numbered_list", "data": ["item1", "item2"] },
    { "type": "nested_list", "data": [ {"text": "parent", "level": 0}, {"text": "child", "level": 1} ] },
    { "type": "hyperlink", "data": { "text": "string", "url": "string" } },
    {
      "type": "table",
      "data": {
        "matrix": [ ["Header1", "Header2"], ["Row1Col1", "Row1Col2"] ], 
        "col_widths": [2.5, 2.5],
        "header_style": { "bg_color": "1F3964", "text_color": "FFFFFF" },
        "cell_customization": [
          { "row": 1, "col": 0, "bg_color": "FAFBFD", "h_align": "center", "v_align": "center" }
        ],
        "borders": { "color": "2E75B6", "size": 4 },
        "merges": []
      }
    }
  ]
}

### FLEXIBILITY RULE:
You can repeat any component type (like 'paragraph', 'heading1', or 'table') inside the "report_structure" array as many times as necessary to complete the user's content. Omit any component type from the array if it is not needed for the content, but never change the schema format.

### EXECUTION COMMAND:
Now, listen to the user request, generate the full content of the report, but output it strictly via this JSON contract. Ensure "page_color" is ALWAYS a valid 6-character hex string (like "FFFFFF") and NEVER null.
"""

excel_prompt = """
You are an Excel JSON generator. Convert the user's request into a JSON object.

OUTPUT RULES:
- Respond ONLY with a valid JSON object inside a single markdown code block.
- No explanation, no intro, just the JSON.

OUTPUT FORMAT:
{
  "sheet_title": "Sales Report",
  "filename": "sales_report.xlsx",
  "theme_color": "1F3964",
  "headers": ["Name", "Department", "Salary", "Status"],
  "rows": [
    ["Ahmed", "Engineering", 5000, "Active"],
    ["Sara",  "Marketing",   4500, "Active"]
  ]
}
"""
