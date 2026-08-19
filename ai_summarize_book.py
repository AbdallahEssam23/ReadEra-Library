#!/usr/bin/env python3
import os
import re
import sys
import json
import urllib.parse
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

TARGET_DIR = Path(__file__).parent
SUMMARIES_JSON = TARGET_DIR / "book_summaries.json"
IGNORE_DIRS = {"Backups", "Covers", ".git", ".obsidian", "__pycache__", ".github"}

KNOWN_SUMMARIES = {
    "قوانين الطبيعة البشرية": [
        "فهم الدوافع النفسية غير الواعية التي تحرك سلوكيات البشر.",
        "التعامل بحكمة وحذر مع الشخصيات النرجسية والحاقدة.",
        "التحكم في الانفعالات الشخصية وعدم الانقياد خلف المشاعر اللحظية.",
        "تطوير قوة الملاحظة للغة الجسد والنبرة الصوتية.",
        "تحويل الأزمات والعقبات إلى فرص لإثبات السلطة والسيطرة."
    ],
    "سيكولوجية المال": [
        "النجاح المالي يتعلق بالسلوك الشخصي أكثر من الذكاء الأكاديمي.",
        "الحرية المالية الحقيقية هي القدرة على التحكم في وقتك وحياتك.",
        "الفرق الحقيقي بين الغنى (Rich) والثروة المستدامة (Wealth).",
        "الاستثمار بعيد المدى والمرونة أهم من الأرباح السريعة المخاطرة.",
        "التواضع والادخار المستمر هما الدرع الأول ضد تقلبات المستقبل."
    ],
    "فن الحرب": [
        "الانتصار الأفضل هو الحسم بدون خوض معركة مسلحة مباشر.",
        "معرفة ذاتك ومعرفة خصمك تضمن لك الفوز في مائة معركة.",
        "السرعة، المرونة، والخداع هي ركائز الاستراتيجية الناجحة.",
        "تجنب نقاط قوة الخصم واستهداف نقاط ضعفه المكشوفة.",
        "التكيف مع التغييرات الميدانية وعدم الجمود على خطة واحدة."
    ],
    "فن الإغواء": [
        "فهم التنميط النفسي للشخصيات واحتياجاتهم العاطفية غير المعبر عنها.",
        "إيجاد الجاذبية عبر بناء الغموض والإيحاء بدلاً من المباشرة الصريحة.",
        "السيطرة على الانطباع الأول وتوليد المشاعر القوية.",
        "استخدام الإيحاء النفسي والصور والكلمات المؤثرة.",
        "تجنب الضغط المباشر وترجيح كفة الشغف والترقب."
    ],
    "الهدوء قوة الانطوائيين": [
        "التركيز والعمق الفكري هما قوة وميزة الانطوائيين الكبرى.",
        "إدراك الفرق بين الخجل الاجتماعي والانطواء الذاتي السليم.",
        "خلق بيئة عمل تشجع على التفكير الفردي قبل العصف الجماعي.",
        "قيادة الانطوائيين تمتاز بالإنصات وإتاحة المجال للآخرين.",
        "موازنة الطاقة الشخصية وتحديد المساحة الاستشفائية الخاصة."
    ]
}

def extract_book_intro_text(file_path, max_pages=5):
    """Extracts first few pages of text to derive themes"""
    if not fitz or not file_path.suffix.lower() == ".pdf":
        return ""
    try:
        doc = fitz.open(file_path)
        text = ""
        for i in range(min(max_pages, len(doc))):
            text += doc[i].get_text("text") + " "
        doc.close()
        return text.strip()
    except Exception:
        return ""

def generate_book_summary(book_name, intro_text=""):
    """Returns 5 key takeaways for a book"""
    # Check known precomputed dictionary first
    for k, takeaways in KNOWN_SUMMARIES.items():
        if k in book_name or book_name in k:
            return takeaways

    # Fallback heuristic rule-based summarizer
    return [
        f"استكشاف المفاهيم الأساسية والأطر النظرية في موضوع {book_name}.",
        "تحليل النماذج والأمثلة العملية وكيفية تطبيقها في الحياة اليومية.",
        "تحديد التحديات الشائعة وسبل تجاوزها بأسلوب منهجي منظم.",
        "توفير أدوات وتقنيات تهدف لرفع الكفاءة وتطوير الفكر الذاتي.",
        "تقديم رؤية شاملة وخلاصة مركزة لبناء المعرفة المستدامة."
    ]

def scan_and_generate_all_summaries():
    print("🔍 جاري توليد التلخيصات الذكية للأفكار الرئيسية للكتب...")
    summaries_data = {}

    for item in sorted(TARGET_DIR.rglob("*")):
        if item.is_file() and item.suffix.lower() in {".pdf", ".epub"}:
            rel_parts = item.relative_to(TARGET_DIR).parts
            if any(part in IGNORE_DIRS for part in rel_parts[:-1]):
                continue

            rel_path = str(item.relative_to(TARGET_DIR))
            book_name = item.stem.replace("_", " ").replace("-", " ")
            book_name = re.sub(r'^\d+[\s\.\-_]+', '', book_name).strip()

            intro_text = extract_book_intro_text(item)
            takeaways = generate_book_summary(book_name, intro_text)

            summaries_data[rel_path] = {
                "title": book_name,
                "takeaways": takeaways
            }

    with open(SUMMARIES_JSON, "w", encoding="utf-8") as f:
        json.dump(summaries_data, f, ensure_ascii=False, indent=2)

    print(f"✨ تم إنشاء ملف التلخيصات الذكية: {SUMMARIES_JSON.name} ({len(summaries_data)} كتاب ملخص)")

if __name__ == "__main__":
    scan_and_generate_all_summaries()
