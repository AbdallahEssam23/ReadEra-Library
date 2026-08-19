#!/usr/bin/env python3
import os
from pathlib import Path
import urllib.parse

# Configuration
TARGET_DIR = Path(__file__).parent
OUTPUT_FILE = TARGET_DIR / "library_catalog.md"
IGNORE_DIRS = {"Backups", "Covers", ".git", ".obsidian"}
BOOK_EXTENSIONS = {".pdf", ".epub", ".mobi", ".azw3", ".djvu", ".txt", ".docx"}

def format_size(size_bytes):
    for unit in ['بايت', 'كيلوبايت', 'ميجابايت', 'جيجابايت']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} تيرابايت"

def clean_name(filename):
    # Remove extension
    name = Path(filename).stem
    # Replace underscores and hyphens with spaces
    name = name.replace('_', ' ').replace('-', ' ')
    # Strip double spaces
    name = " ".join(name.split())
    return name

def scan_library():
    catalog = {}
    total_books = 0
    total_size = 0

    # Walk through the directory
    for item in sorted(TARGET_DIR.iterdir()):
        if item.is_dir() and item.name not in IGNORE_DIRS:
            genre_name = item.name
            books = []
            for file in sorted(item.iterdir()):
                if file.is_file() and file.suffix.lower() in BOOK_EXTENSIONS:
                    clean_title = clean_name(file.name)
                    size = file.stat().st_size
                    relative_path = file.relative_to(TARGET_DIR)
                    # Encode URL path for Markdown compatibility
                    encoded_path = urllib.parse.quote(str(relative_path))
                    
                    books.append({
                        "title": clean_title,
                        "raw_name": file.name,
                        "path": encoded_path,
                        "size": format_size(size),
                        "size_bytes": size,
                        "type": file.suffix.upper()[1:]
                    })
                    total_books += 1
                    total_size += size
            
            if books:
                catalog[genre_name] = books

    return catalog, total_books, total_size

def write_markdown(catalog, total_books, total_size):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# 📚 فهرس المكتبة الرقمية الشخصية\n\n")
        f.write("مرحباً بك في فهرس مكتبتك المنظمة تلقائياً. تم إنشاء هذا الملف لتسهيل تصفح وربط كتبك.\n\n")
        
        # Statistics Table
        f.write("### 📊 إحصائيات المكتبة\n")
        f.write("| الإحصائية | القيمة |\n")
        f.write("| :--- | :--- |\n")
        f.write(f"| **إجمالي الكتب** | {total_books} كتاب |\n")
        f.write(f"| **الحجم الإجمالي** | {format_size(total_size)} |\n")
        f.write(f"| **عدد الأقسام** | {len(catalog)} أقسام |\n\n")
        
        f.write("## 🗂️ الأقسام والكتب\n\n")
        
        for genre, books in catalog.items():
            f.write(f"### 📁 {genre} ({len(books)} كتب)\n")
            f.write("| اسم الكتاب | الصيغة | الحجم | رابط الملف |\n")
            f.write("| :--- | :---: | :---: | :--- |\n")
            for book in books:
                # We use Markdown links
                f.write(f"| **{book['title']}** | `{book['type']}` | {book['size']} | [افتح الكتاب 📖]({book['path']}) |\n")
            f.write("\n---\n\n")
            
    print(f"✅ تم إنشاء الفهرس بنجاح في: {OUTPUT_FILE}")

if __name__ == "__main__":
    catalog, total_books, total_size = scan_library()
    write_markdown(catalog, total_books, total_size)
