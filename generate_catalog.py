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

def write_html_dashboard(library_data, total_books, total_size):
    all_books = []
    all_tags = set()
    category_counts = {}

    for cat, books in library_data.items():
        category_counts[cat] = len(books)
        for b in books:
            book_item = dict(b)
            book_item["category"] = cat
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
    <title>مكتبة الكتب الرقمية - Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
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
            margin-bottom: 2.5rem;
            position: relative;
        }}

        header h1 {{
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #818cf8, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}

        header p {{
            color: var(--text-muted);
            font-size: 1.1rem;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
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

        .search-box {{
            position: relative;
            width: 100%;
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

        .badge.status-badge.active {{
            background: #f59e0b;
            border-color: #f59e0b;
        }}

        .books-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
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

        .status-select {{
            background: #0f172a;
            color: var(--text-main);
            border: 1px solid var(--border-color);
            padding: 0.4rem 0.6rem;
            border-radius: 0.5rem;
            font-size: 0.82rem;
            font-weight: 600;
            outline: none;
            cursor: pointer;
        }}

        .btn-open {{
            display: block;
            text-align: center;
            background: var(--accent-primary);
            color: #fff;
            padding: 0.6rem 1rem;
            border-radius: 0.6rem;
            text-decoration: none;
            font-weight: 700;
            font-size: 0.92rem;
            margin-top: 0.75rem;
            transition: background 0.2s ease;
            cursor: pointer;
            border: none;
            width: 100%;
        }}

        .btn-open:hover {{
            background: var(--accent-hover);
        }}

        .no-results {{
            text-align: center;
            padding: 4rem;
            color: var(--text-muted);
            grid-column: 1 / -1;
            font-size: 1.2rem;
        }}

        /* Modal Styles */
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
            max-width: 550px;
            width: 100%;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
            position: relative;
        }}

        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
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

        .modal-body p {{
            font-size: 0.95rem;
            color: var(--text-muted);
            margin-bottom: 1rem;
            line-height: 1.6;
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

        .btn-copy:hover {{
            background: var(--accent-hover);
        }}
    </style>
</head>
<body>

    <div class="container">
        <header>
            <h1>📚 مكتبة الكتب الرقمية التفاعلية</h1>
            <p>لوحة التحكم والتحليلات والبحث السريع في المكتبة الذكية</p>
        </header>

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
                <div class="stat-icon">⏳</div>
                <div class="stat-info">
                    <h3>قيد القراءة</h3>
                    <p id="readingCount">0 كتاب</p>
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

        <div class="controls-section">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="🔍 ابحث باسم الكتاب، اسم المؤلف، الوسام، أو القسم..." oninput="filterBooks()">
            </div>
            
            <div class="filter-group" id="statusFilters">
                <span class="filter-label">حالة القراءة:</span>
                <span class="badge status-badge active" data-status="ALL" onclick="setStatusFilter('ALL', this)">الكل</span>
                <span class="badge status-badge" data-status="unread" onclick="setStatusFilter('unread', this)">📥 لم يبدأ</span>
                <span class="badge status-badge" data-status="reading" onclick="setStatusFilter('reading', this)">📖 قيد القراءة</span>
                <span class="badge status-badge" data-status="completed" onclick="setStatusFilter('completed', this)">✅ تمت القراءة</span>
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

    <!-- Online Access Info Modal -->
    <div class="modal-overlay" id="accessModal">
        <div class="modal-card">
            <div class="modal-header">
                <div class="modal-title">💡 تنبيه فتح الكتب أونلاين</div>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <p>ملفات الكتب الرقمية (5.64 جيجابايت) متواجدة على **حاسوبك الشخصي وتطبيق ReadEra** على الهاتف وليست مرفوعة لسحابة GitHub الحافظة للمستندات البرمجية.</p>
                <p>لفتح وقراءة الكتب يمكنك:</p>
                <p>1. فتح صفحة <code>index.html</code> مباشرة من حاسوبك المكتبي.</p>
                <p>2. مزامنة المكتبة مع تطبيق **ReadEra** على الهاتف عبر <strong>Syncthing</strong>.</p>
                <div class="modal-path-box" id="modalPathText"></div>
                <button class="btn-copy" id="btnCopyPath" onclick="copyModalPath()">📋 نسخ المسار المحلي للفتح السريع</button>
            </div>
        </div>
    </div>

    <script>
        const booksData = {books_json};
        let currentFormat = 'ALL';
        let currentTag = 'ALL';
        let currentStatus = 'ALL';
        let currentBookRelPath = '';

        function getBookStatus(relPath) {{
            return localStorage.getItem('status_' + relPath) || 'unread';
        }}

        function updateBookStatus(relPath, status) {{
            localStorage.setItem('status_' + relPath, status);
            updateStatsCounts();
            filterBooks();
        }}

        function updateStatsCounts() {{
            let completed = 0;
            let reading = 0;
            booksData.forEach(b => {{
                const st = getBookStatus(b.rel_path);
                if (st === 'completed') completed++;
                if (st === 'reading') reading++;
            }});
            document.getElementById('completedCount').innerText = completed + ' كتاب';
            document.getElementById('readingCount').innerText = reading + ' كتاب';
        }}

        function handleBookClick(urlPath, relPath) {{
            if (window.location.protocol === 'file:') {{
                window.open(urlPath, '_blank');
            }} else {{
                currentBookRelPath = relPath;
                document.getElementById('modalPathText').innerText = relPath;
                document.getElementById('accessModal').style.display = 'flex';
            }}
        }}

        function closeModal() {{
            document.getElementById('accessModal').style.display = 'none';
        }}

        function copyModalPath() {{
            navigator.clipboard.writeText(currentBookRelPath).then(() => {{
                const btn = document.getElementById('btnCopyPath');
                btn.innerText = '✅ تم نسخ المسار المحلي بنجاح!';
                setTimeout(() => {{
                    btn.innerText = '📋 نسخ المسار المحلي للفتح السريع';
                }}, 2000);
            }});
        }}

        function renderBooks(books) {{
            const grid = document.getElementById('booksGrid');
            if (books.length === 0) {{
                grid.innerHTML = '<div class="no-results">❌ لم يتم العثور على أي كتب تطابق البحث والتصفية</div>';
                return;
            }}

            grid.innerHTML = books.map(book => {{
                const status = getBookStatus(book.rel_path);
                const tagsHtml = (book.tags || []).map(t => `<span class="mini-tag">#${{t}}</span>`).join('');

                return `
                <div class="book-card">
                    <div>
                        <div class="book-header">
                            <h3 class="book-title">${{escapeHtml(book.name)}}</h3>
                            <span class="format-tag ${{book.ext}}">${{book.ext}}</span>
                        </div>
                        <div class="book-author">👤 ${{escapeHtml(book.author)}}</div>
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
                        <button class="btn-open" onclick="handleBookClick('${{book.url_path}}', '${{escapeHtml(book.rel_path)}}')">افتح الكتاب 📖</button>
                    </div>
                </div>
            `}}).join('');
        }}

        function filterBooks() {{
            const query = document.getElementById('searchInput').value.toLowerCase().trim();
            const filtered = booksData.filter(book => {{
                const matchesSearch = book.name.toLowerCase().includes(query) ||
                                      book.author.toLowerCase().includes(query) ||
                                      book.category.toLowerCase().includes(query) ||
                                      (book.tags && book.tags.some(t => t.toLowerCase().includes(query)));
                const matchesFormat = currentFormat === 'ALL' || book.ext === currentFormat;
                const matchesTag = currentTag === 'ALL' || (book.tags && book.tags.includes(currentTag));
                const bStatus = getBookStatus(book.rel_path);
                const matchesStatus = currentStatus === 'ALL' || bStatus === currentStatus;

                return matchesSearch && matchesFormat && matchesTag && matchesStatus;
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

        function escapeHtml(text) {{
            return text.replace(/[&<>"']/g, function(m) {{
                return {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }}[m];
            }});
        }}

        // Initial setup
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
