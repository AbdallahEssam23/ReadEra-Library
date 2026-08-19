#!/usr/bin/env python3
import os
import re
import sys
import json
from pathlib import Path

# Configuration
TARGET_DIR = Path(__file__).parent
ROLLBACK_FILE = TARGET_DIR / "rename_rollback.json"
IGNORE_DIRS = {"Backups", "Covers", ".git", ".obsidian"}
BOOK_EXTENSIONS = {".pdf", ".epub", ".mobi", ".azw3", ".djvu", ".txt", ".docx"}

# List of patterns to clean up (case insensitive)
PATTERNS_TO_REMOVE = [
    r'www\.riwaya\.ga',
    r'www\.riwaya\.com',
    r'riwaya\.ga',
    r'FoulaBook\.com',
    r'Foulabook\.com',
    r'foulabook',
    r'FoulaBook',
    r'Copie de ',
    r'lva1[\s\-_]app\d+',
    r'random[\s\-_]\d+[\s\-_]\d+',
    r'كتاب[\s\-_]صيغة[\s\-_]بي[\s\-_]دي[\s\-_]اف[\s\-_]اقرا[\s\-_]اونلاين[\s\-_]pdf\s*\d*',
    r'كتاب[\s\-_]صيغة[\s\-_]مصورة[\s\-_]اقرا[\s\-_]اونلاين',
    r'كتاب[\s\-_]صيغة[\s\-_]بي[\s\-_]دي[\s\-_]اف[\s\-_]اقرا[\s\-_]اونلاين',
    r'صيغة[\s\-_]بي[\s\-_]دي[\s\-_]اف[\s\-_]اقرا[\s\-_]اونلاين',
    r'كتاب[\s\-_]صيغة[\s\-_]بي[\s\-_]دي[\s\-_]اف',
    r'كتاب[\s\-_]صيغة[\s\-_]مصورة',
    r'pdf\s*\d{3,}', # Remove things like pdf 5971
    r'pdf[\s\-_]z[\s\-_]', # Remove "pdf z"
]

def clean_filename(stem):
    original_stem = stem
    
    # 1. Apply regex removals
    for pattern in PATTERNS_TO_REMOVE:
        stem = re.sub(pattern, '', stem, flags=re.IGNORECASE)
        
    # 2. Strip leading numbers (e.g., "001 ", "01- ", "012- ")
    # But do not strip numbers if the filename is JUST numbers
    if not stem.strip().isdigit():
        stem = re.sub(r'^\d+[\s\.\-_]+', '', stem)
        
    # 3. Replace underscores, dashes with spaces
    stem = stem.replace('_', ' ').replace('-', ' ')
    
    # 4. Clean double/triple spaces and strip
    stem = " ".join(stem.split())
    
    # 5. If everything got cleaned out, fall back to original
    if not stem.strip():
        return original_stem
        
    # Remove trailing/leading punctuation that might look bad
    stem = stem.strip(" .-")
    
    return stem

def get_unique_path(parent_dir, stem, suffix, planned_paths):
    """Generates a unique filename if there's a naming collision."""
    candidate_name = f"{stem}{suffix}"
    candidate_path = parent_dir / candidate_name
    
    counter = 1
    # Check both physical files and files we plan to rename in this batch
    while candidate_path.exists() or str(candidate_path) in planned_paths:
        candidate_name = f"{stem} ({counter}){suffix}"
        candidate_path = parent_dir / candidate_name
        counter += 1
        
    return candidate_path

def plan_renames():
    rename_map = []
    planned_destinations = set()
    
    for subdir in sorted(TARGET_DIR.iterdir()):
        if subdir.is_dir() and subdir.name not in IGNORE_DIRS:
            for file in sorted(subdir.iterdir()):
                if file.is_file() and file.suffix.lower() in BOOK_EXTENSIONS:
                    old_stem = file.stem
                    new_stem = clean_filename(old_stem)
                    
                    if old_stem != new_stem:
                        new_path = get_unique_path(subdir, new_stem, file.suffix, planned_destinations)
                        rename_map.append({
                            "old_path": str(file),
                            "new_path": str(new_path),
                            "old_name": file.name,
                            "new_name": new_path.name
                        })
                        planned_destinations.add(str(new_path))
                        
    return rename_map

def execute_renames(rename_map):
    rollback_data = {}
    success_count = 0
    
    for item in rename_map:
        old_path = Path(item["old_path"])
        new_path = Path(item["new_path"])
        
        try:
            old_path.rename(new_path)
            # Store absolute paths in rollback so it is robust
            rollback_data[str(new_path)] = str(old_path)
            success_count += 1
        except Exception as e:
            print(f"❌ فشل نقل: {old_path.name} -> {e}", file=sys.stderr)
            
    # Save rollback map
    if rollback_data:
        with open(ROLLBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(rollback_data, f, ensure_ascii=False, indent=4)
            
    return success_count

def rollback():
    if not ROLLBACK_FILE.exists():
        print("❌ لا يوجد ملف تراجع (rollback) متاح.")
        return
        
    with open(ROLLBACK_FILE, "r", encoding="utf-8") as f:
        rollback_data = json.load(f)
        
    success_count = 0
    for current_path_str, original_path_str in rollback_data.items():
        current_path = Path(current_path_str)
        original_path = Path(original_path_str)
        
        if current_path.exists():
            try:
                # Ensure parent directory exists for rollback
                original_path.parent.mkdir(parents=True, exist_ok=True)
                current_path.rename(original_path)
                success_count += 1
            except Exception as e:
                print(f"❌ فشل استعادة: {current_path.name} -> {e}", file=sys.stderr)
        else:
            print(f"⚠️ الملف غير موجود حالياً للاستعادة: {current_path.name}")
            
    # Clean up rollback file
    ROLLBACK_FILE.unlink(missing_ok=True)
    print(f"🔄 تم التراجع بنجاح عن {success_count} ملفاً وإعادتها لأسماءها السابقة.")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--revert":
        rollback()
        return
        
    commit_mode = len(sys.argv) > 1 and sys.argv[1] == "--commit"
    
    print("🔍 جاري فحص ملفات الكتب والتخطيط لإعادة تسميتها...")
    rename_map = plan_renames()
    
    if not rename_map:
        print("✨ جميع الملفات نظيفة بالفعل! لا توجد ملفات تحتاج لتعديل.")
        return
        
    if not commit_mode:
        print(f"\n📊 تم العثور على {len(rename_map)} ملفاً تحتاج إلى تنظيف أسماءها:")
        print("-" * 80)
        # Show first 15 files as preview
        for item in rename_map[:15]:
            print(f"❌ القديم: {item['old_name']}")
            print(f"✅ الجديد: {item['new_name']}")
            print("-" * 80)
            
        if len(rename_map) > 15:
            print(f"... وهناك {len(rename_map) - 15} ملفات أخرى.")
            
        print("\n⚠️ تنبيه: هذه معاينة فقط (Dry Run). لم يتم تغيير أي ملفات بعد.")
        print("👉 لتطبيق التعديلات وتنظيف الأسماء فعلياً، أعد تشغيل السكربت مع خيار --commit:")
        print("   python3 clean_filenames.py --commit")
        print("\n💡 السكربت آمن؛ سيقوم بإنشاء ملف تراجع تلقائي تالياً في حال أردت التراجع عن التسمية لاحقاً.")
    else:
        print(f"🚀 جاري تنظيف وإعادة تسمية {len(rename_map)} ملفاً...")
        success = execute_renames(rename_map)
        print(f"🎉 اكتمل التعديل بنجاح! تم تنظيف {success} ملفاً.")
        print(f"💾 تم حفظ ملف التراجع في: {ROLLBACK_FILE.name}")
        print("💡 للتراجع عن هذا التعديل في أي وقت وإعادة الأسماء القديمة، تشغيل:")
        print("   python3 clean_filenames.py --revert")

if __name__ == "__main__":
    main()
