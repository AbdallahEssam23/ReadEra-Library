#!/usr/bin/env python3
import os
import re
from pathlib import Path

TARGET_DIR = Path(__file__).parent

def organize_tasawwuf():
    tasawwuf_dir = TARGET_DIR / "تصوف"
    if not tasawwuf_dir.exists():
        return

    subcategories = {
        "أوراد_وأحزاب_ودعوات": [r'حزب', r'أحزاب', r'ورد', r'أوراد', r'دعاء', r'صلوات', r'وظيفة', r'مناجاة', r'الورد', r'الأحزاب'],
        "شروح_وتفاسير": [r'شرح', r'شروح', r'حاشية', r'تفسير', r'مفتاح', r'بيان', r'فتح', r'تنوير', r'إعجاز'],
        "سير_ومناقب_الأعلام": [r'مناقب', r'سيرة', r'ترجمة', r'طبقات', r'الشيخ', r'الإمام', r'ترجمة'],
        "ديوانات_وأشعار": [r'ديوان', r'شعر', r'قصائد', r'قصيدة', r'تائية', r'همزية', r'البردة', r'أشعار'],
        "رسائل_وحكم_ومكتوبات": [r'رسالة', r'رسائل', r'مكتوبات', r'الحكم', r'وصية', r'نصيحة', r'رساله']
    }

    # Create subdirectories
    for sub in subcategories:
        (tasawwuf_dir / sub).mkdir(exist_ok=True)
    
    # General subfolder for rest to keep top level clean
    general_dir = tasawwuf_dir / "كتب_ومؤلفات_عامة"
    general_dir.mkdir(exist_ok=True)

    moved_count = 0
    for file in list(tasawwuf_dir.iterdir()):
        if file.is_file() and file.suffix.lower() in {".pdf", ".epub", ".mobi", ".azw3", ".djvu", ".txt"}:
            filename = file.name
            matched = False
            
            for sub_name, keywords in subcategories.items():
                pattern = "|".join(keywords)
                if re.search(pattern, filename, re.IGNORECASE):
                    dest = tasawwuf_dir / sub_name / file.name
                    file.rename(dest)
                    matched = True
                    moved_count += 1
                    break
            
            if not matched:
                dest = general_dir / file.name
                file.rename(dest)
                moved_count += 1

    print(f"✅ تم تنظيم قسم تصوف: نقل {moved_count} كتاباً إلى مجلدات فرعية متخصصة.")

def organize_shayateen():
    shayateen_dir = TARGET_DIR / "سلسلة رواية – الشياطين"
    if not shayateen_dir.exists():
        return

    subfolders = {
        "الأجزاء_01_إلى_25": range(1, 26),
        "الأجزاء_26_إلى_50": range(26, 51),
        "الأجزاء_51_إلى_75": range(51, 76),
        "الأجزاء_76_فما_فوق": range(76, 500)
    }

    for sub in subfolders:
        (shayateen_dir / sub).mkdir(exist_ok=True)
        
    special_dir = shayateen_dir / "روايات_خاصة"
    special_dir.mkdir(exist_ok=True)

    moved_count = 0
    for file in list(shayateen_dir.iterdir()):
        if file.is_file() and file.suffix.lower() in {".pdf", ".epub", ".mobi", ".azw3"}:
            filename = file.name
            # Try to extract starting number
            match = re.match(r'^(\d+)', filename)
            moved = False
            if match:
                num = int(match.group(1))
                for sub_name, rng in subfolders.items():
                    if num in rng:
                        file.rename(shayateen_dir / sub_name / file.name)
                        moved = True
                        moved_count += 1
                        break
            if not moved:
                file.rename(special_dir / file.name)
                moved_count += 1

    print(f"✅ تم تنظيم قسم سلسلة الشياطين: نقل {moved_count} رواية إلى مجلدات أجزاء مرتبة.")

if __name__ == "__main__":
    organize_tasawwuf()
    organize_shayateen()
