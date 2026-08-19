#!/usr/bin/env python3
import os
import re
import sys
import json
import urllib.parse
from pathlib import Path
from datetime import datetime

TARGET_DIR = Path(__file__).parent
OBSIDIAN_NOTES_DIR = TARGET_DIR / "Obsidian_Reading_Notes"
READERA_EXPORTS_DIR = TARGET_DIR / "ReadEra_Exports"

def ensure_directories():
    OBSIDIAN_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    READERA_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_filename(name):
    clean = re.sub(r'[\\/*?:"<>|]', '_', name)
    return clean.strip()

def parse_readera_json(json_path):
    """
    Parses ReadEra exported JSON notes file.
    Expected structure may contain books with list of quotes/bookmarks/notes.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        notes = []
        if isinstance(data, list):
            for item in data:
                notes.append({
                    "book_title": item.get("book", item.get("title", "كتاب غير مسمى")),
                    "author": item.get("author", "مؤلف غير معروف"),
                    "quote": item.get("quote", item.get("text", "")),
                    "note": item.get("note", item.get("comment", "")),
                    "page": item.get("page", ""),
                    "date": item.get("date", datetime.now().strftime("%Y-%m-%d"))
                })
        elif isinstance(data, dict):
            # Check for nested keys
            books = data.get("books", data.get("documents", [data]))
            for b in books:
                title = b.get("title", b.get("name", "كتاب غير مسمى"))
                author = b.get("author", "مؤلف غير معروف")
                quotes = b.get("quotes", b.get("notes", b.get("highlights", [])))
                for q in quotes:
                    if isinstance(q, str):
                        notes.append({"book_title": title, "author": author, "quote": q, "note": "", "date": datetime.now().strftime("%Y-%m-%d")})
                    elif isinstance(q, dict):
                        notes.append({
                            "book_title": title,
                            "author": author,
                            "quote": q.get("text", q.get("quote", "")),
                            "note": q.get("comment", q.get("note", "")),
                            "page": q.get("page", ""),
                            "date": q.get("date", datetime.now().strftime("%Y-%m-%d"))
                        })
        return notes
    except Exception as e:
        print(f"⚠️ تعذر قراءة ملف {json_path.name}: {e}")
        return []

def generate_obsidian_note(book_title, author, category, quotes_list, tags=None):
    """
    Generates a rich, PARA/Zettelkasten compliant Obsidian Markdown note for a book.
    """
    safe_title = sanitize_filename(book_title)
    note_path = OBSIDIAN_NOTES_DIR / f"{safe_title}.md"
    tags = tags if tags else ["ملاحظات_قراءة", "كتب"]
    tags_str = " ".join([f"#{t}" for t in tags])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    content = f"""---
title: "{book_title}"
author: "{author}"
category: "{category}"
date_updated: "{now_str}"
tags:
  - ملاحظات_قراءة
  - كتب
---

# 📚 {book_title}

> **اسم المؤلف:** {author}  
> **القسم:** `{category}`  
> **تاريخ التحديث:** `{now_str}`  
> **الوسوم:** {tags_str}

---

## 💡 الملخص والانطباع الشخصي

*اكتب هنا ملخصك أو انطباعك العام عن الكتاب...*

---

## ✍️ الاقتباسات والملاحظات المستخرجة من ReadEra

"""

    if quotes_list:
        for idx, q in enumerate(quotes_list, 1):
            quote_text = q.get("quote", "").strip()
            comment = q.get("note", "").strip()
            page = f" (صفحة {q['page']})" if q.get("page") else ""
            date_str = q.get("date", "")

            content += f"### 📌 اقتباس #{idx}{page}\n"
            content += f"> {quote_text}\n\n"
            if comment:
                content += f"**💬 تعليق/ملاحظة:** {comment}\n\n"
            content += f"*تاريخ التدوين: {date_str}*\n\n---\n\n"
    else:
        content += "> 📥 *لا توجد اقتباسات مستخرجة بعد. قم بتسجيل وتصدير اقتباساتك من تطبيق ReadEra لتظهر هنا تلقائياً.*\n\n"

    with open(note_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return note_path

def create_sample_readera_export():
    """Creates a sample export JSON file if ReadEra_Exports directory is empty"""
    sample_file = READERA_EXPORTS_DIR / "sample_readera_export.json"
    if not sample_file.exists():
        sample_data = [
            {
                "title": "قوانين الطبيعة البشرية",
                "author": "روبرت غرين",
                "quote": "إن تقبل الآخرين كما هم، مع إدراك عيوبهم وحقائق نفوسهم، هو مفتاح القوة والسلطة الشخصية.",
                "note": "قاعدة ممتازة في التعامل مع الشخصيات النرجسية.",
                "page": 45,
                "date": datetime.now().strftime("%Y-%m-%d")
            },
            {
                "title": "سيكولوجية المال",
                "author": "مورجان هوسل",
                "quote": "الأنفاق بأقل مما تكسب هو اللبنة الأولى لبناء الحرية المالية الحقيقية.",
                "note": "مفهوم الحرية أهم من الاستهلاك المظهري.",
                "page": 112,
                "date": datetime.now().strftime("%Y-%m-%d")
            }
        ]
        with open(sample_file, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
        print(f"💡 تم إنشاء ملف نموذج لتصدير MOCK: {sample_file.relative_to(TARGET_DIR)}")

def main():
    ensure_directories()
    create_sample_readera_export()

    print("🔍 جاري فحص ملفات تصدير MOCK والملاحظات من ReadEra...")
    found_exports = list(READERA_EXPORTS_DIR.glob("*.json"))
    total_notes_exported = 0

    books_notes = {}

    for export_file in found_exports:
        parsed_notes = parse_readera_json(export_file)
        for n in parsed_notes:
            title = n.get("book_title")
            if title not in books_notes:
                books_notes[title] = {
                    "author": n.get("author", "غير محدد"),
                    "category": "عام",
                    "quotes": []
                }
            books_notes[title]["quotes"].append(n)

    for title, b_data in books_notes.items():
        note_p = generate_obsidian_note(title, b_data["author"], b_data["category"], b_data["quotes"])
        total_notes_exported += len(b_data["quotes"])
        print(f"✅ تم إنشاء/تحديث بطاقة Obsidian: {note_p.relative_to(TARGET_DIR)} ({len(b_data['quotes'])} اقتباسات)")

    print("\n" + "="*60)
    print(f"✨ تم تحويل وتصدير {total_notes_exported} اقتباس وملاحظة إلى Obsidian Markdown بنجاح!")
    print(f"📁 المسار المستهدف لملاحظات Obsidian: {OBSIDIAN_NOTES_DIR.relative_to(TARGET_DIR)}/")

if __name__ == "__main__":
    main()
