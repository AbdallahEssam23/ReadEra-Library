#!/usr/bin/env python3
import os
import re
import sys
import hashlib
from pathlib import Path

TARGET_DIR = Path(__file__).parent
IGNORE_DIRS = {"Backups", "Covers", ".git", ".obsidian", "__pycache__", ".github"}
BOOK_EXTENSIONS = {".pdf", ".epub", ".mobi", ".azw3", ".djvu", ".txt", ".docx"}

PROMOTIONAL_PATTERNS = [
    r'freebookar\.online', r'pdf\s*z', r'^\d+[\s\._\-]+', r'\[\d+\]',
    r'[\._\-\s]*1$', r'[\._\-\s]*_1$', r'\(1\)$', r'كتاب صيغة مصورة اقرا  اونلاين'
]

def calculate_full_hash(filepath):
    """Calculate full SHA256 of file for guaranteed exact match"""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def score_filepath(filepath):
    """
    Score a filepath: higher score means BETTER quality path/filename.
    Factors:
    - Cleaner filename (fewer promotional words or digit prefixes) -> +score
    - Deeper/specific subfolder vs root folder -> +score
    - Standard title length -> +score
    """
    score = 0
    name = filepath.name
    rel_path = str(filepath.relative_to(TARGET_DIR))

    # Bonus for subfolder organization (deeper path)
    depth = len(filepath.relative_to(TARGET_DIR).parts)
    score += depth * 10

    # Penalty for promotional tags
    for pat in PROMOTIONAL_PATTERNS:
        if re.search(pat, name, re.IGNORECASE):
            score -= 25

    # Penalty for copy indicators like " 1.pdf", "_1.pdf", "(1).pdf"
    if re.search(r'[\s_\-\(]1[\.\)]', name):
        score -= 30

    # Prefer Arabic characters over raw digits/hashes
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', name))
    score += arabic_chars * 2

    # Shorter clean name is usually cleaner
    score -= len(name) * 0.1

    return score

def find_duplicates():
    print("🔍 جاري فحص الملفات المكررة بالكامل عبر التوقيع الرقمي (SHA-256)...")
    hashes = {}
    total_scanned = 0

    for item in sorted(TARGET_DIR.rglob("*")):
        if item.is_file() and item.suffix.lower() in BOOK_EXTENSIONS:
            rel_parts = item.relative_to(TARGET_DIR).parts
            if any(part in IGNORE_DIRS for part in rel_parts[:-1]):
                continue

            total_scanned += 1
            file_size = item.stat().st_size
            # Quick tuple check: size + file header hash
            with open(item, 'rb') as f:
                header = f.read(256 * 1024)
            quick_hash = (file_size, hashlib.md5(header).hexdigest())

            if quick_hash not in hashes:
                hashes[quick_hash] = []
            hashes[quick_hash].append(item)

    # Now verify with full sha256 for groups > 1
    duplicate_groups = []
    for paths in hashes.values():
        if len(paths) > 1:
            # Full verification
            full_map = {}
            for p in paths:
                sha = calculate_full_hash(p)
                full_map.setdefault(sha, []).append(p)
            for dup_list in full_map.values():
                if len(dup_list) > 1:
                    duplicate_groups.append(dup_list)

    return total_scanned, duplicate_groups

def main():
    commit = "--commit" in sys.argv
    total_scanned, dup_groups = find_duplicates()

    total_dups = sum(len(g) - 1 for g in dup_groups)
    print(f"📊 إجمالي الملفات المفحوصة: {total_scanned}")
    print(f"⚠️ عدد مجموعات الملفات المكررة تماماً: {len(dup_groups)}")
    print(f"🗑️ إجمالي الملفات الزائدة القابلة للحذف: {total_dups}\n")

    if not dup_groups:
        print("🎉 لم يتم العثور على أي ملفات مكررة! المكتبة نظيفة بالكامل.")
        return

    to_delete = []
    for idx, group in enumerate(dup_groups, 1):
        # Sort paths by score descending
        scored_paths = sorted(group, key=lambda p: score_filepath(p), reverse=True)
        keep = scored_paths[0]
        remove_list = scored_paths[1:]

        print(f"--- مجموعة {idx} ({len(group)} نسخ) ---")
        print(f"  ✅ الإبقاء على النسخة الأفضل: {keep.relative_to(TARGET_DIR)}")
        for r in remove_list:
            print(f"  ❌ حذف النسخة المكررة: {r.relative_to(TARGET_DIR)}")
            to_delete.append(r)

    print("\n" + "="*60)
    if commit:
        print(f"🚀 جاري حذف {len(to_delete)} ملف مكرر بنجاح...")
        deleted_count = 0
        freed_bytes = 0
        for path in to_delete:
            try:
                freed_bytes += path.stat().st_size
                path.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"⚠️ تعذر حذف {path.name}: {e}")

        mb_freed = freed_bytes / (1024 * 1024)
        print(f"✨ تم حذف {deleted_count} ملف مكرر بنجاح وتوفير {mb_freed:.2f} ميجابايت من المساحة!")
    else:
        print(f"💡 هذه معاينة تجريبية (Dry Run). لم يتم حذف أي ملفات بعد.")
        print("تشغيل الأمر الحقيقي لإزالة التكرارات:")
        print("  python3 deduplicate_books.py --commit")

if __name__ == "__main__":
    main()
