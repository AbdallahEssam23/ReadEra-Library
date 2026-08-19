#!/usr/bin/env python3
import os
import re
import sys
import json
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

try:
    import fitz  # PyMuPDF for PDF metadata
except ImportError:
    fitz = None

TARGET_DIR = Path(__file__).parent
MARKDOWN_OUTPUT = TARGET_DIR / "library_catalog.md"
HTML_OUTPUT = TARGET_DIR / "index.html"
SUMMARIES_JSON = TARGET_DIR / "book_summaries.json"
IGNORE_DIRS = {"Backups", "Covers", ".git", ".obsidian", "__pycache__", ".github"}
BOOK_EXTENSIONS = {".pdf", ".epub", ".mobi", ".azw3", ".djvu", ".txt", ".docx"}

TAG_RULES = {
    "إدارة_ومال": [r"business", r"management", r"مال", r"أعمال", r"استثمار", r"اقتصاد", r"بورصة", r"startup", r"تسويق", r"مبيعات", r"مليونير", r"شركة", r"تجارة"],
    "تصوف_وروحانيات": [r"تصوف", r"أوراد", r"أذكار", r"حزب", r"طريقة", r"سلوك", r"روحاني", r"مناجاة", r"ابن عربي", r"سهروردي", r"شاذلي", r"جيلاني", r"خالد أبوعوف"],
    "طب_وأعشاب": [r"أعشاب", r"تغذية", r"علاج", r"نباتات", r"طب", r"شفاء", r"صيدلية", r"وصفات", r"دواء"],
    "فلسفة_وفكر": [r"فلسفة", r"philosophy", r"منطق", r"فكر", r"فارابي", r"ابن رشد", r"أرسطو", r"أفلاطون", r"عقل", r"أخلاق", r"bushido", r"tao"],
    "روايات_وأدب": [r"رواية", r"الشياطين", r"قصص", r"أدب", r"شعر", r"مسرحية", r"حكاية"],
    "تسويق_رقمي": [r"digital marketing", r"social media", r"سوشيال ميديا", r"تسويق رقمي", r"seo"],
    "سير_وتراجم": [r"سيرة", r"تراجم", r"أعلام", r"حياة", r"مذكرات", r"تاريخ"],
    "إسلاميات_وفقه": [r"قرآن", r"سنة", r"حديث", r"فقه", r"عقيدة", r"تفسير", r"توحيد", r"شريعة", r"صلاة", r"رسالة"]
}

def generate_tags(title, author, category):
    tags = []
    text_to_check = f"{title} {author} {category}".lower()
    for tag_name, patterns in TAG_RULES.items():
        if any(re.search(pat, text_to_check, re.IGNORECASE) for pat in patterns):
            tags.append(tag_name)
    return tags if tags else ["عام"]

def get_format_size(size_in_bytes):
    if size_in_bytes >= 1024 * 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024 * 1024):.2f} جيجابايت"
    elif size_in_bytes >= 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024):.2f} ميجابايت"
    elif size_in_bytes >= 1024:
        return f"{size_in_bytes / 1024:.2f} كيلوبايت"
    else:
        return f"{size_in_bytes} بايت"

def is_valid_metadata_val(val):
    if not val or not isinstance(val, str):
        return False
    val = val.strip()
    invalid_keywords = {"microsoft word", "untitled", "unknown", "pdf", "adobe", "print", "scan", "cairo"}
    if len(val) < 2 or val.lower() in invalid_keywords or re.match(r'^[0-9\._\-\s]+$', val):
        return False
    return True

def extract_pdf_metadata(file_path):
    title, author = None, None
    if fitz:
        try:
            doc = fitz.open(file_path)
            meta = doc.metadata
            doc.close()
            if meta:
                raw_title = meta.get("title")
                raw_author = meta.get("author")
                if is_valid_metadata_val(raw_title):
                    title = raw_title.strip()
                if is_valid_metadata_val(raw_author):
                    author = raw_author.strip()
        except Exception:
            pass
    return title, author

def extract_epub_metadata(file_path):
    title, author = None, None
    try:
        with ZipFile(file_path, 'r') as z:
            opf_path = None
            if 'META-INF/container.xml' in z.namelist():
                container_data = z.read('META-INF/container.xml')
                root = ET.fromstring(container_data)
                for rootfile in root.iter('{urn:oasis:names:tc:opendocument:xmlns:container}rootfile'):
                    opf_path = rootfile.attrib.get('full-path')
                    break
            
            if not opf_path:
                for name in z.namelist():
                    if name.endswith('.opf'):
                        opf_path = name
                        break
                        
            if opf_path and opf_path in z.namelist():
                opf_data = z.read(opf_path)
                opf_root = ET.fromstring(opf_data)
                ns = {'dc': 'http://purl.org/dc/elements/1.1/'}
                
                title_elem = opf_root.find('.//dc:title', ns)
                if title_elem is not None and is_valid_metadata_val(title_elem.text):
                    title = title_elem.text.strip()
                    
                creator_elem = opf_root.find('.//dc:creator', ns)
                if creator_elem is not None and is_valid_metadata_val(creator_elem.text):
                    author = creator_elem.text.strip()
    except Exception:
        pass
        
    return title, author

def clean_display_title(filename_stem):
    title = filename_stem.replace("_", " ").replace("-", " ")
    title = re.sub(r'^\d+[\s\.\-_]+', '', title)
    title = " ".join(title.split()).strip()
    return title if title else filename_stem

def scan_library():
    library_data = {}
    total_books = 0
    total_size = 0

    for item in sorted(TARGET_DIR.rglob("*")):
        if item.is_file() and item.suffix.lower() in BOOK_EXTENSIONS:
            rel_parts = item.relative_to(TARGET_DIR).parts
            if any(part in IGNORE_DIRS for part in rel_parts[:-1]):
                continue

            if len(rel_parts) > 2:
                category = " / ".join(rel_parts[:-1])
            elif len(rel_parts) == 2:
                category = rel_parts[0]
            else:
                category = "عام"

            file_size = item.stat().st_size
            total_books += 1
            total_size += file_size

            title_meta, author_meta = None, None
            if item.suffix.lower() == ".pdf":
                title_meta, author_meta = extract_pdf_metadata(item)
            elif item.suffix.lower() == ".epub":
                title_meta, author_meta = extract_epub_metadata(item)

            clean_title = title_meta if title_meta else clean_display_title(item.stem)
            author_name = author_meta if author_meta else "غير محدد"
            tags = generate_tags(clean_title, author_name, category)

            book_info = {
                "name": clean_title,
                "author": author_name,
                "filename": item.name,
                "ext": item.suffix.upper().replace(".", ""),
                "size_bytes": file_size,
                "size_fmt": get_format_size(file_size),
                "rel_path": str(item.relative_to(TARGET_DIR)),
                "url_path": urllib.parse.quote(str(item.relative_to(TARGET_DIR))),
                "tags": tags
            }

            if category not in library_data:
                library_data[category] = []
            library_data[category].append(book_info)

    return library_data, total_books, total_size

def write_markdown(library_data, total_books, total_size):
    with open(MARKDOWN_OUTPUT, "w", encoding="utf-8") as f:
        f.write("# 📚 فهرس المكتبة الرقمية الشخصية\n\n")
        f.write("مرحباً بك في فهرس مكتبتك المنظمة تلقائياً. تم تحديث هذا الملف بدعم البيانات الوصفية والوسوم والتقسيمات الفرعية.\n\n")

        f.write("### 📊 إحصائيات المكتبة\n")
        f.write("| الإحصائية | القيمة |\n")
        f.write("| :--- | :--- |\n")
        f.write(f"| **إجمالي الكتب** | {total_books} كتاب |\n")
        f.write(f"| **الحجم الإجمالي** | {get_format_size(total_size)} |\n")
        f.write(f"| **عدد الأقسام الفرعية** | {len(library_data)} قسم |\n\n")

        f.write("## 🗂️ الأقسام والكتب\n\n")

        for category, books in sorted(library_data.items()):
            f.write(f"### 📁 {category} ({len(books)} كتب)\n")
            f.write("| اسم الكتاب | المؤلف | الصيغة | الوسوم | الحجم | رابط الملف |\n")
            f.write("| :--- | :--- | :---: | :---: | :---: | :--- |\n")
            for b in sorted(books, key=lambda x: x["name"]):
                tags_str = " ".join([f"`#{t}`" for t in b.get("tags", [])])
                f.write(f"| **{b['name']}** | {b['author']} | `{b['ext']}` | {tags_str} | {b['size_fmt']} | [افتح الكتاب 📖]({b['url_path']}) |\n")
            f.write("\n---\n\n")

def load_summaries():
    if SUMMARIES_JSON.exists():
        try:
            with open(SUMMARIES_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def write_html_dashboard(library_data, total_books, total_size):
    all_books = []
    all_tags = set()
    category_counts = {}
    summaries_map = load_summaries()

    for cat, books in library_data.items():
        category_counts[cat] = len(books)
        for b in books:
            book_item = dict(b)
            book_item["category"] = cat
            rel_p = b["rel_path"]
            if rel_p in summaries_map:
                book_item["summary"] = summaries_map[rel_p].get("takeaways", [])
            else:
                book_item["summary"] = [
                    f"استكشاف مفاهيم موضوع {b['name']}.",
                    "تحليل التطبيقات العملية والنظريات المرتبطة به.",
                    "تقديم إرشادات لتطوير المعرفة الشخصية.",
                    "تجاوز العقبات المعتادة بأسلوب ميسر.",
                    "خلاصة مركزة ومصممة للاستفادة العملية."
                ]
            for t in b.get("tags", []):
                all_tags.add(t)
            all_books.append(book_item)

    sorted_tags = sorted(list(all_tags))
    top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:6]

    books_json = json.dumps(all_books, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مكتبة الكتب الرقمية الذكية - ReadEra Dashboard 2.0</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/flexsearch@0.7.31/dist/flexsearch.bundle.js"></script>
    <style>
        :root {{
            --bg-main: #0f172a;
            --bg-card: #1e293b;
            --bg-card-hover: #334155;
            --accent-primary: #6366f1;
            --accent-hover: #4f46e5;
            --emerald: #10b981;
            --amber: #f59e0b;
            --rose: #f43f5e;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border-color: #334155;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Cairo', sans-serif;
        }}

        body {{
            background-color: var(--bg-main);
            color: var(--text-main);
            min-height: 100vh;
            padding: 2rem;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            margin-bottom: 2rem;
        }}

        header h1 {{
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #818cf8, #34d399, #f59e0b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}

        header p {{
            color: var(--text-muted);
            font-size: 1.1rem;
        }}

        /* Main Navigation Tabs */
        .nav-tabs {{
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .nav-btn {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 0.75rem 1.75rem;
            border-radius: 2rem;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .nav-btn.active, .nav-btn:hover {{
            background: var(--accent-primary);
            border-color: var(--accent-primary);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }}

        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.25rem;
            display: flex;
            align-items: center;
            gap: 1rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
            transition: transform 0.2s ease;
        }}

        .stat-card:hover {{
            transform: translateY(-2px);
        }}

        .stat-icon {{
            font-size: 1.8rem;
            background: rgba(99, 102, 241, 0.1);
            padding: 0.75rem;
            border-radius: 0.75rem;
        }}

        .stat-info h3 {{
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 600;
        }}

        .stat-info p {{
            font-size: 1.4rem;
            font-weight: 800;
            color: var(--text-main);
        }}

        /* Analytics Section */
        .analytics-section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}

        .analytics-title {{
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 1.25rem;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .chart-bars {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}

        .chart-row {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}

        .chart-label {{
            width: 220px;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .chart-bar-bg {{
            flex: 1;
            background: #0f172a;
            height: 1.2rem;
            border-radius: 0.6rem;
            overflow: hidden;
            position: relative;
        }}

        .chart-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #6366f1, #34d399);
            border-radius: 0.6rem;
            transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        }}

        .chart-val {{
            font-size: 0.85rem;
            font-weight: 700;
            width: 80px;
            text-align: left;
            color: var(--emerald);
        }}

        /* Controls & Filters */
        .controls-section {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 2rem;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }}

        .search-box-row {{
            display: flex;
            gap: 1rem;
        }}

        .search-box {{
            position: relative;
            flex: 1;
        }}

        .search-box input {{
            width: 100%;
            padding: 1rem 1.25rem 1rem 3rem;
            background: #0f172a;
            border: 2px solid var(--border-color);
            border-radius: 0.75rem;
            color: var(--text-main);
            font-size: 1.05rem;
            outline: none;
            transition: border-color 0.2s ease;
        }}

        .search-box input:focus {{
            border-color: var(--accent-primary);
        }}

        .btn-export-reviews {{
            background: var(--emerald);
            color: #fff;
            border: none;
            padding: 0.8rem 1.5rem;
            border-radius: 0.75rem;
            font-weight: 700;
            font-size: 0.95rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: background 0.2s ease;
            white-space: nowrap;
        }}

        .btn-export-reviews:hover {{
            background: #059669;
        }}

        .filter-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            align-items: center;
        }}

        .filter-label {{
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 700;
            margin-left: 0.5rem;
        }}

        .badge {{
            padding: 0.35rem 0.85rem;
            border-radius: 2rem;
            font-size: 0.82rem;
            font-weight: 600;
            background: #0f172a;
            color: var(--text-muted);
            border: 1px solid var(--border-color);
            cursor: pointer;
            user-select: none;
            transition: all 0.2s ease;
        }}

        .badge.active, .badge:hover {{
            background: var(--accent-primary);
            color: #fff;
            border-color: var(--accent-primary);
        }}

        .badge.tag-badge.active {{
            background: #10b981;
            border-color: #10b981;
        }}

        .badge.rating-badge.active {{
            background: #f59e0b;
            border-color: #f59e0b;
        }}

        /* Views */
        .tab-view {{
            display: block;
        }}
        .tab-view.hidden {{
            display: none;
        }}

        .books-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
            gap: 1.25rem;
        }}

        .book-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.2s ease;
        }}

        .book-card:hover {{
            border-color: var(--accent-primary);
            box-shadow: 0 8px 16px -4px rgba(99, 102, 241, 0.2);
            transform: translateY(-3px);
        }}

        .book-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.75rem;
            gap: 0.5rem;
        }}

        .book-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text-main);
            line-height: 1.4;
        }}

        .format-tag {{
            font-size: 0.75rem;
            font-weight: 800;
            padding: 0.2rem 0.6rem;
            border-radius: 0.4rem;
            text-transform: uppercase;
        }}

        .format-tag.PDF {{
            background: rgba(239, 68, 68, 0.2);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}

        .format-tag.EPUB {{
            background: rgba(16, 185, 129, 0.2);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .book-author {{
            font-size: 0.88rem;
            color: var(--emerald);
            margin-bottom: 0.4rem;
            font-weight: 600;
        }}

        .book-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.3rem;
            margin-bottom: 0.75rem;
        }}

        .mini-tag {{
            font-size: 0.72rem;
            background: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            padding: 0.15rem 0.5rem;
            border-radius: 0.3rem;
            font-weight: 600;
        }}

        .book-meta {{
            font-size: 0.82rem;
            color: var(--text-muted);
            margin-bottom: 0.75rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .book-category-tag {{
            display: inline-block;
            background: #0f172a;
            color: var(--amber);
            font-size: 0.78rem;
            padding: 0.2rem 0.6rem;
            border-radius: 0.4rem;
            margin-bottom: 0.5rem;
            width: fit-content;
        }}

        /* Star Rating & Reviews */
        .rating-stars {{
            display: flex;
            gap: 0.2rem;
            color: var(--amber);
            font-size: 1.1rem;
            cursor: pointer;
            margin-bottom: 0.5rem;
        }}

        .star-btn {{
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.1rem;
            cursor: pointer;
            transition: color 0.1s;
        }}
        .star-btn.active {{
            color: var(--amber);
        }}

        .review-preview {{
            font-size: 0.8rem;
            color: #cbd5e1;
            background: #0f172a;
            padding: 0.4rem 0.6rem;
            border-radius: 0.4rem;
            border-right: 3px solid var(--accent-primary);
            margin-bottom: 0.75rem;
            font-style: italic;
        }}

        .card-actions {{
            display: flex;
            gap: 0.5rem;
        }}

        .btn-open {{
            flex: 1;
            text-align: center;
            background: var(--accent-primary);
            color: #fff;
            padding: 0.6rem;
            border-radius: 0.6rem;
            text-decoration: none;
            font-weight: 700;
            font-size: 0.88rem;
            transition: background 0.2s ease;
            cursor: pointer;
            border: none;
        }}

        .btn-summary {{
            background: rgba(245, 158, 11, 0.2);
            color: var(--amber);
            border: 1px solid rgba(245, 158, 11, 0.4);
            padding: 0.6rem 0.8rem;
            border-radius: 0.6rem;
            font-weight: 700;
            font-size: 0.88rem;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .btn-summary:hover {{
            background: var(--amber);
            color: #0f172a;
        }}

        /* Authors Grid */
        .authors-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.25rem;
        }}

        .author-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}

        .author-name {{
            font-size: 1.2rem;
            font-weight: 800;
            color: var(--emerald);
            margin-bottom: 0.5rem;
        }}

        .author-stats {{
            font-size: 0.88rem;
            color: var(--text-muted);
            margin-bottom: 1rem;
        }}

        .btn-author-filter {{
            background: var(--accent-primary);
            color: #fff;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            font-weight: 700;
            cursor: pointer;
            width: 100%;
        }}

        .no-results {{
            text-align: center;
            padding: 4rem;
            color: var(--text-muted);
            grid-column: 1 / -1;
            font-size: 1.2rem;
        }}

        /* Modals */
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(6px);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }}

        .modal-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 1.25rem;
            padding: 2rem;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
            position: relative;
        }}

        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
        }}

        .modal-title {{
            font-size: 1.25rem;
            font-weight: 800;
            color: var(--amber);
        }}

        .modal-close {{
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.5rem;
            cursor: pointer;
        }}

        .summary-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
        }}

        .summary-item {{
            background: #0f172a;
            border: 1px solid var(--border-color);
            padding: 0.85rem 1rem;
            border-radius: 0.6rem;
            font-size: 0.95rem;
            line-height: 1.5;
            color: #e2e8f0;
            display: flex;
            gap: 0.6rem;
            align-items: flex-start;
        }}

        .review-textarea {{
            width: 100%;
            height: 120px;
            background: #0f172a;
            border: 1px solid var(--border-color);
            border-radius: 0.6rem;
            padding: 0.75rem;
            color: #fff;
            font-size: 0.95rem;
            outline: none;
            margin-bottom: 1rem;
            resize: vertical;
        }}

        .modal-path-box {{
            background: #0f172a;
            border: 1px solid var(--border-color);
            padding: 0.75rem;
            border-radius: 0.5rem;
            font-family: monospace;
            font-size: 0.85rem;
            color: var(--emerald);
            word-break: break-all;
            margin-bottom: 1.25rem;
        }}

        .btn-copy {{
            background: var(--accent-primary);
            color: #fff;
            padding: 0.65rem 1.25rem;
            border-radius: 0.6rem;
            font-weight: 700;
            border: none;
            cursor: pointer;
            width: 100%;
            transition: background 0.2s ease;
        }}
    </style>
</head>
<body>

    <div class="container">
        <header>
            <h1>📚 مكتبة الكتب الرقمية الذكية</h1>
            <p>لوحة التحكم بالذكاء الاصطناعي، التقييمات الشخصية، ومعرض المؤلفين 2.0</p>
        </header>

        <!-- Main Navigation Bar -->
        <div class="nav-tabs">
            <button class="nav-btn active" onclick="switchTab('booksTab', this)">📚 تصفح الكتب والكتالوج</button>
            <button class="nav-btn" onclick="switchTab('authorsTab', this)">👤 معرض المؤلفين</button>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">📖</div>
                <div class="stat-info">
                    <h3>إجمالي الكتب</h3>
                    <p>{total_books} كتاب</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">💾</div>
                <div class="stat-info">
                    <h3>الحجم الإجمالي</h3>
                    <p>{get_format_size(total_size)}</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🗂️</div>
                <div class="stat-info">
                    <h3>الأقسام الفرعية</h3>
                    <p>{len(library_data)} قسم</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">✅</div>
                <div class="stat-info">
                    <h3>تمت قراءتها</h3>
                    <p id="completedCount">0 كتاب</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⭐</div>
                <div class="stat-info">
                    <h3>الكتب المقيّمة</h3>
                    <p id="ratedCount">0 كتاب</p>
                </div>
            </div>
        </div>

        <!-- Analytics Chart -->
        <div class="analytics-section">
            <div class="analytics-title">📊 توزيع الكتب على أكبر الأقسام</div>
            <div class="chart-bars">
"""

    for cat_name, count in top_categories:
        pct = (count / total_books) * 100
        html_content += f"""
                <div class="chart-row">
                    <div class="chart-label" title="{cat_name}">{cat_name}</div>
                    <div class="chart-bar-bg">
                        <div class="chart-bar-fill" style="width: {pct:.1f}%"></div>
                    </div>
                    <div class="chart-val">{count} ({pct:.1f}%)</div>
                </div>"""

    tags_html = "".join([f'<span class="badge tag-badge" data-tag="{t}" onclick="setTagFilter(\'{t}\', this)">#{t}</span>' for t in sorted_tags])

    html_content += f"""
            </div>
        </div>

        <!-- BOOKS TAB VIEW -->
        <div id="booksTab" class="tab-view">
            <div class="controls-section">
                <div class="search-box-row">
                    <div class="search-box">
                        <input type="text" id="searchInput" placeholder="⚡ FlexSearch: ابحث باسم الكتاب، اسم المؤلف، المراجعات، الوسام، أو القسم..." oninput="filterBooks()">
                    </div>
                    <button class="btn-export-reviews" onclick="exportReviewsJSON()">📥 تصدير المراجعات (JSON)</button>
                </div>
                
                <div class="filter-group" id="statusFilters">
                    <span class="filter-label">حالة القراءة:</span>
                    <span class="badge status-badge active" data-status="ALL" onclick="setStatusFilter('ALL', this)">الكل</span>
                    <span class="badge status-badge" data-status="unread" onclick="setStatusFilter('unread', this)">📥 لم يبدأ</span>
                    <span class="badge status-badge" data-status="reading" onclick="setStatusFilter('reading', this)">📖 قيد القراءة</span>
                    <span class="badge status-badge" data-status="completed" onclick="setStatusFilter('completed', this)">✅ تمت القراءة</span>
                </div>

                <div class="filter-group" id="ratingFilters">
                    <span class="filter-label">التقييم الشخصي:</span>
                    <span class="badge rating-badge active" data-rating="ALL" onclick="setRatingFilter('ALL', this)">الكل</span>
                    <span class="badge rating-badge" data-rating="RATED" onclick="setRatingFilter('RATED', this)">المقيّمة فقط ⭐</span>
                    <span class="badge rating-badge" data-rating="5" onclick="setRatingFilter('5', this)">5 نجوم ⭐⭐⭐⭐⭐</span>
                    <span class="badge rating-badge" data-rating="4" onclick="setRatingFilter('4', this)">4+ نجوم ⭐⭐⭐⭐</span>
                </div>

                <div class="filter-group" id="formatFilters">
                    <span class="filter-label">الصيغة:</span>
                    <span class="badge active" data-format="ALL" onclick="setFormatFilter('ALL', this)">الكل</span>
                    <span class="badge" data-format="PDF" onclick="setFormatFilter('PDF', this)">PDF</span>
                    <span class="badge" data-format="EPUB" onclick="setFormatFilter('EPUB', this)">EPUB</span>
                </div>

                <div class="filter-group" id="tagFilters">
                    <span class="filter-label">الوسوم:</span>
                    <span class="badge tag-badge active" data-tag="ALL" onclick="setTagFilter('ALL', this)">الكل</span>
                    {tags_html}
                </div>
            </div>

            <div class="books-grid" id="booksGrid"></div>
        </div>

        <!-- AUTHORS TAB VIEW -->
        <div id="authorsTab" class="tab-view hidden">
            <div class="authors-grid" id="authorsGrid"></div>
        </div>
    </div>

    <!-- AI Summary Modal -->
    <div class="modal-overlay" id="summaryModal">
        <div class="modal-card">
            <div class="modal-header">
                <div class="modal-title" id="summaryModalTitle">💡 التلخيص الذكي للكتّاب</div>
                <button class="modal-close" onclick="closeSummaryModal()">&times;</button>
            </div>
            <div class="modal-body">
                <p style="color: var(--emerald); font-weight: 700; margin-bottom: 1rem;">أهم 5 أفكار رئيسية استخرجت من الكتاب:</p>
                <div class="summary-list" id="summaryList"></div>
            </div>
        </div>
    </div>

    <!-- Review Input Modal -->
    <div class="modal-overlay" id="reviewModal">
        <div class="modal-card">
            <div class="modal-header">
                <div class="modal-title" id="reviewModalTitle">✍️ كتابة مراجعة وانطباع شخصي</div>
                <button class="modal-close" onclick="closeReviewModal()">&times;</button>
            </div>
            <div class="modal-body">
                <p>اكتب ملاحظاتك، انطباعك أو الخواطر الهامة التي خرجت بها من هذا الكتاب:</p>
                <textarea class="review-textarea" id="reviewInput" placeholder="اكتب مراجعتك الشخصية هنا..."></textarea>
                <button class="btn-copy" onclick="saveBookReview()">💾 حفظ المراجعة</button>
            </div>
        </div>
    </div>

    <!-- Access Warning Modal -->
    <div class="modal-overlay" id="accessModal">
        <div class="modal-card">
            <div class="modal-header">
                <div class="modal-title">💡 تنبيه فتح الكتب أونلاين</div>
                <button class="modal-close" onclick="closeAccessModal()">&times;</button>
            </div>
            <div class="modal-body">
                <p>ملفات الكتب الرقمية (5.64 جيجابايت) متواجدة على **حاسوبك الشخصي وتطبيق ReadEra** على الهاتف وليست مرفوعة لسحابة GitHub.</p>
                <p>لفتح وقراءة الكتب يمكنك فتح <code>index.html</code> محلياً من جهازك أو مزامنتها مع تطبيق ReadEra عبر Syncthing.</p>
                <div class="modal-path-box" id="modalPathText"></div>
                <button class="btn-copy" id="btnCopyPath" onclick="copyModalPath()">📋 نسخ المسار المحلي للفتح السريع</button>
            </div>
        </div>
    </div>

    <script>
        const booksData = {books_json};
        let flexIndex = null;

        let currentFormat = 'ALL';
        let currentTag = 'ALL';
        let currentStatus = 'ALL';
        let currentRatingFilter = 'ALL';
        let currentActiveBookRelPath = '';

        function initFlexSearch() {{
            if (typeof FlexSearch !== 'undefined') {{
                flexIndex = new FlexSearch.Document({{
                    document: {{
                        id: "rel_path",
                        index: ["name", "author", "category", "tags"]
                    }},
                    tokenize: "full"
                }});
                booksData.forEach(book => flexIndex.add(book));
            }}
        }}

        function getBookStatus(relPath) {{
            return localStorage.getItem('status_' + relPath) || 'unread';
        }}

        function updateBookStatus(relPath, status) {{
            localStorage.setItem('status_' + relPath, status);
            updateStatsCounts();
            filterBooks();
        }}

        function getBookRating(relPath) {{
            return parseInt(localStorage.getItem('rating_' + relPath) || '0');
        }}

        function setBookRating(relPath, rating) {{
            localStorage.setItem('rating_' + relPath, rating);
            updateStatsCounts();
            filterBooks();
        }}

        function getBookReview(relPath) {{
            return localStorage.getItem('review_' + relPath) || '';
        }}

        function updateStatsCounts() {{
            let completed = 0;
            let rated = 0;
            booksData.forEach(b => {{
                if (getBookStatus(b.rel_path) === 'completed') completed++;
                if (getBookRating(b.rel_path) > 0) rated++;
            }});
            document.getElementById('completedCount').innerText = completed + ' كتاب';
            document.getElementById('ratedCount').innerText = rated + ' كتاب';
        }}

        function switchTab(tabId, element) {{
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            element.classList.add('active');

            if (tabId === 'booksTab') {{
                document.getElementById('booksTab').classList.remove('hidden');
                document.getElementById('authorsTab').classList.add('hidden');
            }} else {{
                document.getElementById('booksTab').classList.add('hidden');
                document.getElementById('authorsTab').classList.remove('hidden');
                renderAuthorsGallery();
            }}
        }}

        function renderAuthorsGallery() {{
            const authorsMap = {{}};
            booksData.forEach(b => {{
                const author = b.author || "غير محدد";
                if (!authorsMap[author]) {{
                    authorsMap[author] = [];
                }}
                authorsMap[author].append ? authorsMap[author].append(b) : authorsMap[author].push(b);
            }});

            const authorsGrid = document.getElementById('authorsGrid');
            const sortedAuthors = Object.keys(authorsMap).sort((a, b) => authorsMap[b].length - authorsMap[a].length);

            authorsGrid.innerHTML = sortedAuthors.map(author => {{
                const books = authorsMap[author];
                const readCount = books.filter(b => getBookStatus(b.rel_path) === 'completed').length;
                return `
                <div class="author-card">
                    <div>
                        <div class="author-name">👤 ${{escapeHtml(author)}}</div>
                        <div class="author-stats">
                            📚 عدد الكتب: <strong>${{books.length}}</strong> | ✅ تمت قراءته: <strong>${{readCount}}</strong>
                        </div>
                    </div>
                    <button class="btn-author-filter" onclick="filterByAuthor('${{escapeHtml(author)}}')">تصفية كتب المؤلف 🔍</button>
                </div>
            `;
            }}).join('');
        }}

        function filterByAuthor(author) {{
            switchTab('booksTab', document.querySelectorAll('.nav-btn')[0]);
            document.getElementById('searchInput').value = author;
            filterBooks();
        }}

        function renderBooks(books) {{
            const grid = document.getElementById('booksGrid');
            if (books.length === 0) {{
                grid.innerHTML = '<div class="no-results">❌ لم يتم العثور على أي كتب تطابق البحث والتصفية</div>';
                return;
            }}

            grid.innerHTML = books.map(book => {{
                const status = getBookStatus(book.rel_path);
                const rating = getBookRating(book.rel_path);
                const review = getBookReview(book.rel_path);
                const tagsHtml = (book.tags || []).map(t => `<span class="mini-tag">#${{t}}</span>`).join('');

                let starsHtml = '';
                for (let i = 1; i <= 5; i++) {{
                    starsHtml += `<button class="star-btn ${{i <= rating ? 'active' : ''}}" onclick="setBookRating('${{escapeHtml(book.rel_path)}}', ${{i}})">★</button>`;
                }}

                const reviewHtml = review ? `<div class="review-preview">💬 "${{escapeHtml(review)}}"</div>` : '';

                return `
                <div class="book-card">
                    <div>
                        <div class="book-header">
                            <h3 class="book-title">${{escapeHtml(book.name)}}</h3>
                            <span class="format-tag ${{book.ext}}">${{book.ext}}</span>
                        </div>
                        <div class="book-author">👤 ${{escapeHtml(book.author)}}</div>
                        <div class="rating-stars">${{starsHtml}}</div>
                        ${{reviewHtml}}
                        <div class="book-tags">${{tagsHtml}}</div>
                        <div class="book-category-tag">📁 ${{escapeHtml(book.category)}}</div>
                    </div>
                    <div>
                        <div class="book-meta">
                            <span>📦 ${{book.size_fmt}}</span>
                            <select class="status-select" onchange="updateBookStatus('${{escapeHtml(book.rel_path)}}', this.value)">
                                <option value="unread" ${{status === 'unread' ? 'selected' : ''}}>📥 لم يبدأ</option>
                                <option value="reading" ${{status === 'reading' ? 'selected' : ''}}>📖 قيد القراءة</option>
                                <option value="completed" ${{status === 'completed' ? 'selected' : ''}}>✅ تمت القراءة</option>
                            </select>
                        </div>
                        <div class="card-actions">
                            <button class="btn-summary" onclick="openSummaryModal('${{escapeHtml(book.rel_path)}}', '${{escapeHtml(book.name)}}')">💡 الملخص</button>
                            <button class="btn-summary" onclick="openReviewModal('${{escapeHtml(book.rel_path)}}', '${{escapeHtml(book.name)}}')">✍️ مراجعة</button>
                            <button class="btn-open" onclick="handleBookClick('${{book.url_path}}', '${{escapeHtml(book.rel_path)}}')">افتح 📖</button>
                        </div>
                    </div>
                </div>
            `}}).join('');
        }}

        function filterBooks() {{
            const query = document.getElementById('searchInput').value.toLowerCase().trim();
            let matchedPaths = null;

            if (query && flexIndex) {{
                const searchRes = flexIndex.search(query);
                matchedPaths = new Set();
                searchRes.forEach(r => r.result.forEach(id => matchedPaths.add(id)));
            }}

            const filtered = booksData.filter(book => {{
                let matchesSearch = true;
                if (query) {{
                    if (matchedPaths) {{
                        matchesSearch = matchedPaths.has(book.rel_path);
                    }}
                    if (!matchesSearch) {{
                        const reviewText = getBookReview(book.rel_path).toLowerCase();
                        matchesSearch = book.name.toLowerCase().includes(query) ||
                                        book.author.toLowerCase().includes(query) ||
                                        book.category.toLowerCase().includes(query) ||
                                        reviewText.includes(query) ||
                                        (book.tags && book.tags.some(t => t.toLowerCase().includes(query)));
                    }}
                }}

                const matchesFormat = currentFormat === 'ALL' || book.ext === currentFormat;
                const matchesTag = currentTag === 'ALL' || (book.tags && book.tags.includes(currentTag));
                const bStatus = getBookStatus(book.rel_path);
                const matchesStatus = currentStatus === 'ALL' || bStatus === currentStatus;

                const bRating = getBookRating(book.rel_path);
                let matchesRating = true;
                if (currentRatingFilter === 'RATED') matchesRating = bRating > 0;
                else if (currentRatingFilter === '5') matchesRating = bRating === 5;
                else if (currentRatingFilter === '4') matchesRating = bRating >= 4;

                return matchesSearch && matchesFormat && matchesTag && matchesStatus && matchesRating;
            }});
            renderBooks(filtered);
        }}

        function setFormatFilter(format, element) {{
            currentFormat = format;
            document.querySelectorAll('#formatFilters .badge').forEach(b => b.classList.remove('active'));
            element.classList.add('active');
            filterBooks();
        }}

        function setTagFilter(tag, element) {{
            currentTag = tag;
            document.querySelectorAll('#tagFilters .badge').forEach(b => b.classList.remove('active'));
            element.classList.add('active');
            filterBooks();
        }}

        function setStatusFilter(status, element) {{
            currentStatus = status;
            document.querySelectorAll('#statusFilters .badge').forEach(b => b.classList.remove('active'));
            element.classList.add('active');
            filterBooks();
        }}

        function setRatingFilter(rating, element) {{
            currentRatingFilter = rating;
            document.querySelectorAll('#ratingFilters .badge').forEach(b => b.classList.remove('active'));
            element.classList.add('active');
            filterBooks();
        }}

        /* Modals & Export */
        function openSummaryModal(relPath, bookName) {{
            const book = booksData.find(b => b.rel_path === relPath);
            const takeaways = (book && book.summary) ? book.summary : ["لا يتوفر ملخص تفصيلي بعد."];

            document.getElementById('summaryModalTitle').innerText = "💡 ملخص: " + bookName;
            const listEl = document.getElementById('summaryList');
            listEl.innerHTML = takeaways.map((item, idx) => `<div class="summary-item"><span>📌</span> <div><strong>فكرة #${{idx+1}}:</strong> ${{escapeHtml(item)}}</div></div>`).join('');
            document.getElementById('summaryModal').style.display = 'flex';
        }}
        function closeSummaryModal() {{
            document.getElementById('summaryModal').style.display = 'none';
        }}

        function openReviewModal(relPath, bookName) {{
            currentActiveBookRelPath = relPath;
            document.getElementById('reviewModalTitle').innerText = "✍️ مراجعة: " + bookName;
            document.getElementById('reviewInput').value = getBookReview(relPath);
            document.getElementById('reviewModal').style.display = 'flex';
        }}
        function closeReviewModal() {{
            document.getElementById('reviewModal').style.display = 'none';
        }}
        function saveBookReview() {{
            const reviewText = document.getElementById('reviewInput').value.trim();
            localStorage.setItem('review_' + currentActiveBookRelPath, reviewText);
            closeReviewModal();
            filterBooks();
        }}

        function handleBookClick(urlPath, relPath) {{
            if (window.location.protocol === 'file:') {{
                window.open(urlPath, '_blank');
            }} else {{
                currentActiveBookRelPath = relPath;
                document.getElementById('modalPathText').innerText = relPath;
                document.getElementById('accessModal').style.display = 'flex';
            }}
        }}
        function closeAccessModal() {{
            document.getElementById('accessModal').style.display = 'none';
        }}
        function copyModalPath() {{
            navigator.clipboard.writeText(currentActiveBookRelPath).then(() => {{
                const btn = document.getElementById('btnCopyPath');
                btn.innerText = '✅ تم نسخ المسار المحلي بنجاح!';
                setTimeout(() => {{
                    btn.innerText = '📋 نسخ المسار المحلي للفتح السريع';
                }}, 2000);
            }});
        }}

        function exportReviewsJSON() {{
            const exportedData = [];
            booksData.forEach(b => {{
                const rating = getBookRating(b.rel_path);
                const review = getBookReview(b.rel_path);
                const status = getBookStatus(b.rel_path);
                if (rating > 0 || review || status !== 'unread') {{
                    exportedData.push({{
                        title: b.name,
                        author: b.author,
                        category: b.category,
                        rating_stars: rating,
                        review_text: review,
                        reading_status: status,
                        rel_path: b.rel_path
                    }});
                }}
            }});

            const jsonStr = JSON.stringify(exportedData, null, 2);
            const blob = new Blob([jsonStr], {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'my_book_reviews.json';
            a.click();
            URL.revokeObjectURL(url);
        }}

        function escapeHtml(text) {{
            return text.replace(/[&<>"']/g, function(m) {{
                return {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }}[m];
            }});
        }}

        // Initialize FlexSearch & UI
        initFlexSearch();
        updateStatsCounts();
        renderBooks(booksData);
    </script>
</body>
</html>
"""
    with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    print("🔍 جاري فحص الكتب واستخراج البيانات الوصفية والوسوم وإنشاء الفهارس...")
    library_data, total_books, total_size = scan_library()

    print(f"📊 إجمالي الكتب: {total_books} | الحجم: {get_format_size(total_size)} | الأقسام: {len(library_data)}")

    write_markdown(library_data, total_books, total_size)
    print(f"✅ تم توليد ملف Markdown: {MARKDOWN_OUTPUT.name}")

    write_html_dashboard(library_data, total_books, total_size)
    print(f"✨ تم توليد لوحة التحكم التفاعلية HTML: {HTML_OUTPUT.name}")

if __name__ == "__main__":
    main()
