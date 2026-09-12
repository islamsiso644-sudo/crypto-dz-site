#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
حقن كود إعلان A-ADS ثابتًا في صفحات الموقع
==========================================
لماذا هذا السكربت؟
- بوت التحقق لدى A-ADS يقرأ مصدر الصفحة (ولا ينفذ الجافاسكريبت دائمًا)،
  لذا الحقن الثابت في HTML هو الطريقة المضمونة لاعتبار الوحدة مثبتة
  وبدء احتساب الانطباعات والأرباح.
- يقرأ الكود من data/config.json (المصدر الوحيد للحقيقة).
- Idempotent: تشغيله مرارًا لا يكرر الإعلان — يعبّئ الخانات الفارغة فقط
  ويُحدّث الكود إن تغيّر في الإعدادات.

ملاحظة مهمة: خانة إعلان articles/price-report.html تقع داخل منطقة
REPORT_DATA_START/END التي يعيد الناشر اليومي توليدها (auto_publisher.py)،
لذا يجب تشغيل هذا السكربت بعده دائمًا (وهذا ما يفعله .github/workflows/daily-update.yml).

الاستخدام:
    python3 inject_ads.py          # حقن الكود في كل الصفحات
    python3 inject_ads.py --clean  # إزالة الإعلانات وإرجاع الخانات الفارغة
"""

import json
import re
import sys
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parent
CONFIG = SITE_ROOT / "data" / "config.json"

# علامات داخل الخانات المعبأة (تسهّل التحديث والتنظيف)
FILLED_START = "<!-- AD_INJECT_START -->"
FILLED_END = "<!-- AD_INJECT_END -->"

# خانة فارغة (بأحد التنسيقين المستخدمين في الموقع)
EMPTY_SLOT = re.compile(r'<div class="(container ad-slot|ad-slot)"\s*>\s*</div>')
# خانة معبأة (من هذا السكربت) — الوسم الافتتاحي + العلامات + الوسم الختامي
FILLED_SLOT = re.compile(
    r'(<div class="(container ad-slot|ad-slot)[^"]*"[^>]*>)\s*' 
    + re.escape(FILLED_START) + r'(.*?)' + re.escape(FILLED_END)
    + r'\s*(</div>)',
    re.DOTALL,
)

HTML_FILES = [
    "index.html",
    "articles.html",
    "about.html",
    "contact.html",
    "privacy.html",
    "articles/crypto-beginners.html",
    "articles/crypto-safety.html",
    "articles/freelance-taxes.html",
    "articles/legal-status.html",
    "articles/online-shopping.html",
    "articles/payoneer-vs-others.html",
    "articles/price-report.html",
    "articles/redotpay-guide.html",
    "articles/scam-alerts.html",
    "articles/usdt-to-baridi-mob.html",
    "articles/withdraw-adsense.html",
]


def load_ad_code() -> str:
    """قراءة كود الإعلان من config.json."""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    return (cfg.get("aads_code") or "").strip()


def normalize(code: str) -> str:
    """توحيد المسافات لمقارنة موثوقة."""
    return re.sub(r"\s+", " ", code).strip()


def make_opening_filled(open_tag: str) -> str:
    """إضافة class filled لوسم الخانة الافتتاحي إن لم يكن موجودًا."""
    if "filled" in open_tag:
        return open_tag
    return open_tag.replace("ad-slot", "ad-slot filled", 1)


def make_opening_plain(open_tag: str) -> str:
    """إزالة class filled عند التنظيف."""
    return open_tag.replace("ad-slot filled", "ad-slot", 1)


def process_file(path: Path, ad_code: str, clean: bool):
    """حقن/تحديث/تنظيف خانات ملف واحد. يرجع (عدد الخانات، هل تغيّر الملف)."""
    text = path.read_text(encoding="utf-8")
    original = text

    # 1) معالجة الخانات المعبأة: تحديث الكود إن تغيّر — أو تفريغها في وضع التنظيف
    out = []
    pos = 0
    for m in FILLED_SLOT.finditer(text):
        out.append(text[pos:m.start()])
        open_tag, _, inner, close_tag = m.group(1), m.group(2), m.group(3), m.group(4)
        if clean:
            out.append(make_opening_plain(open_tag) + close_tag)
        else:
            current = inner.strip()
            if normalize(current) != normalize(ad_code):
                out.append(make_opening_filled(open_tag) + "\n"
                           + FILLED_START + "\n" + ad_code + "\n" + FILLED_END
                           + "\n" + close_tag)
            else:
                # الكود مطابق — فقط نضمن وجود class filled
                out.append(make_opening_filled(open_tag) + "\n"
                           + FILLED_START + inner + FILLED_END
                           + "\n" + close_tag)
        pos = m.end()
    out.append(text[pos:])
    text = "".join(out)

    # 2) تعبئة الخانات الفارغة (في وضع الحقن فقط)
    if not clean:
        def fill(m):
            open_tag = make_opening_filled(m.group(0)[:m.group(0).index(">") + 1])
            return (open_tag + "\n" + FILLED_START + "\n" + ad_code + "\n"
                    + FILLED_END + "\n</div>")
        text = EMPTY_SLOT.sub(fill, text)

    changed = text != original
    if changed:
        path.write_text(text, encoding="utf-8")

    slots = len(EMPTY_SLOT.findall(text)) + len(FILLED_SLOT.findall(text))
    return slots, changed


def main():
    clean = "--clean" in sys.argv
    print("=== حقن إعلانات A-ADS ===")
    ad_code = ""
    if clean:
        print("الوضع: تنظيف (إزالة الإعلانات وإرجاع الخانات فارغة)")
    else:
        ad_code = load_ad_code()
        if not ad_code:
            print("✗ لا يوجد كود إعلان في data/config.json — لا شيء لحقنه.")
            sys.exit(1)
        print(f"✓ كود الإعلان مقروء من data/config.json ({len(ad_code)} حرفًا)")

    files_changed = 0
    total_slots = 0
    for rel in HTML_FILES:
        path = SITE_ROOT / rel
        if not path.exists():
            print(f"⚠ غير موجود (تخطي): {rel}")
            continue
        slots, changed = process_file(path, ad_code, clean)
        total_slots += slots
        if changed:
            files_changed += 1
            action = "نُظّفت" if clean else "حُقن/حُدّث"
            print(f"✓ {rel}: {action} ({slots} خانة)")
        else:
            print(f"  {rel}: لا تغيير ({slots} خانة)")

    if clean:
        print(f"=== تم التنظيف: {files_changed} ملفًا عُدّل ===")
    else:
        print(f"=== تم: {files_changed} ملفًا عُدّل، {total_slots} خانة إعلانية جاهزة ===")


if __name__ == "__main__":
    main()
