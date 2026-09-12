#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
كريبتو جازاير — الناشر الآلي اليومي
====================================
يجلب أسعار الكريبتو من CoinGecko وسعر صرف الدينار من open.er-api.com،
ثم يحدّث صفحة تقرير الأسعار articles/price-report.html بين علامتين آمنتين:
    <!-- REPORT_DATA_START --> ... <!-- REPORT_DATA_END -->
التصميم يجعل البوت آمنًا: لا يمكنه كسر الصفحة أبدًا لأنه يستبدل فقط
المحتوى بين العلامتين، وإن فشل أي استدعاء API يترك المحتوى السابق كما هو.

التشغيل المحلي:  python3 auto_publisher.py
التشغيل الآلي :  GitHub Actions يوميًا (انظر .github/workflows/daily-update.yml)
"""

import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ---------- الإعدادات ----------
COINS = [
    ("bitcoin",     "بيتكوين BTC",   "₿"),
    ("ethereum",    "إيثريوم ETH",   "Ξ"),
    ("tether",      "تيثر USDT",     "₮"),
    ("binancecoin", "بينانس BNB",    "B"),
    ("solana",      "سولانا SOL",    "◎"),
]
SITE_ROOT = Path(__file__).resolve().parent          # جذر الموقع
REPORT    = SITE_ROOT / "articles" / "price-report.html"
ARCHIVE   = SITE_ROOT / "articles.html"
START_MARK = "<!-- REPORT_DATA_START -->"
END_MARK   = "<!-- REPORT_DATA_END -->"
DZD_PARALLEL_PREMIUM = 1.35   # علاوة تقديرية للسوق الموازية (توضَّح للقارئ بأنها تقديرية)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) crypto-dz-bot/1.0"}


def http_json(url, timeout=20):
    """جلب JSON مع مهلة ومحاولات متعددة."""
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last_err = e
    raise RuntimeError(f"فشل جلب {url}: {last_err}")


def fetch_prices():
    """أسعار الكريبتو بالدولار + تغير 24 ساعة من CoinGecko."""
    ids = ",".join(c[0] for c in COINS)
    url = (f"https://api.coingecko.com/api/v3/simple/price"
           f"?ids={ids}&vs_currencies=usd&include_24hr_change=true")
    data = http_json(url)
    out = []
    for cid, ar_name, sym in COINS:
        row = data.get(cid)
        if not row or "usd" not in row:
            continue
        out.append({
            "id": cid, "name": ar_name, "sym": sym,
            "usd": float(row["usd"]),
            "chg": float(row.get("usd_24h_change") or 0.0),
        })
    return out


def fetch_dzd():
    """سعر صرف الدولار الرسمي مقابل الدينار الجزائري."""
    data = http_json("https://open.er-api.com/v6/latest/USD")
    rate = data.get("rates", {}).get("DZD")
    if not rate:
        raise RuntimeError("لم يُعثر على DZD في استجابة الصرف")
    return float(rate)


def fmt_usd(v):
    if v >= 1000:
        return f"{v:,.0f}"
    if v >= 1:
        return f"{v:,.2f}"
    return f"{v:.4f}"


def build_report_html(prices, dzd, now):
    """بناء محتوى التقرير (HTML عربي RTL) — يُزرع بين العلامتين."""
    p = {r["id"]: r for r in prices}
    btc, eth = p.get("bitcoin"), p.get("ethereum")
    usdt = p.get("tether")

    # سطر افتتاحي متغير حسب حركة السوق (يمنع تكرار الجُمل نفسها كل يوم)
    if btc and eth:
        if btc["chg"] > 1 and eth["chg"] > 1:
            mood = "يوم أخضر واضح في السوق"
        elif btc["chg"] < -1 and eth["chg"] < -1:
            mood = "يوم أحمر في السوق"
        sentence = f"أنهى السوق {mood}، مع تغير بيتكوين {btc['chg']:+.2f}% وإيثريوم {eth['chg']:+.2f}% خلال 24 ساعة."
    else:
        sentence = "تقرير اليوم آلي بالكامل من مصادر مباشرة."

    parallel = dzd * DZD_PARALLEL_PREMIUM
    dzd_str = f"{dzd:,.2f}"
    par_str = f"{parallel:,.0f}"

    # جدول الأسعار
    rows = ""
    for r in prices:
        chg_cls = "up" if r["chg"] >= 0 else "down"
        arrow = "▲" if r["chg"] >= 0 else "▼"
        dzd_price = r["usd"] * dzd
        rows += (
            f'<tr><td><span class="coin-cell">{r["sym"]} {r["name"]}</span></td>'
            f'<td>{fmt_usd(r["usd"])} $</td>'
            f'<td><span class="{chg_cls}">{arrow} {abs(r["chg"]):.2f}%</span></td>'
            f'<td>{dzd_price:,.0f} دج</td></tr>\n'
        )

    # فقرة استنتاج قابلة للتغير (تحليل آلي بسيط للنزعة)
    if btc:
        if btc["chg"] >= 2:
            trend_txt = "صاعد"
            trend_tip = "الصعود الحاد خلال 24 ساعة ليس دعوة شراء؛ مراقبة هادئة أرخص من اندفاع متأخر."
        elif btc["chg"] <= -2:
            trend_txt = "هابط"
            trend_tip = "هبوط اليوم لا يعني نهاية شيء؛ من يحتفظ بـ USDT لنقل أمواله لا يتأثر به عمليًا."
        else:
            trend_txt = "مستقر نسبيًا"
            trend_tip = "استقرار الأسعار جيد لمن يستعمل الكريبتو وسيلة نقل أموال: تكلفة توقيتك منخفضة اليوم."
        analysis = (f'بقراءة آلية لتغير 24 ساعة، النزعة العامة اليوم <strong>{trend_txt}</strong>. '
                    f'{trend_tip}')
    else:
        analysis = ""

    date_ar = now.strftime("%Y/%m/%d — %H:%M UTC")
    html = f"""
<div class="article-meta-report">
  <p>أنشئ آليًا في {date_ar} من مصادر مباشرة (CoinGecko لأسعار العملات، وER-API لسعر الصرف الرسمي). الأسعار للأسف التداول، وليست نصيحة استثمارية.</p>
</div>

{sentence}

<h2>جدول أسعار اليوم (USD + دج بالسعر الرسمي)</h2>
<div class="table-wrap">
<table>
  <thead><tr><th>العملة</th><th>السعر بالدولار</th><th>تغير 24 ساعة</th><th>قيمتها بالدينار (رسمي)</th></tr></thead>
  <tbody>
{rows}  </tbody>
</table>
</div>

<h2>سعر الدولار مقابل الدينار</h2>
<p>السعر الرسمي اليوم: <strong>1 USD = {dzd_str} دج</strong>. أما سعر السوق الموازية المقدَّر تقريبيًا فيجلس حوالي <strong>{par_str} دج</strong> — رقم تقديري للاسترشاد فقط، والسعر الفعلي يُحدَّد لحظة الاتفاق مع الصرّاف (<a href="usdt-to-baridi-mob.html">دليل التعامل مع الصرافين</a>).</p>

<h2>قراءة آلية سريعة</h2>
<p>{analysis}</p>

<h2>ملاحظات عملية لليوم</h2>
<ul>
  <li><strong>TRC20 تبقى الأرخص:</strong> رسوم النقل بين المحافظ تُقاس بالسنتات — استعملها ما لم يفرض المرسل غير ذلك.</li>
  <li><strong>لا تحتفظ بـ USDT بلا حاجة:</strong> دورتها العملية جزائريًا قصيرة — استلم، حوّل إلى دينار، انتهى.</li>
  <li><strong>التحقق قبل الإرسال:</strong> أول وآخر 6 أحرف من العنوان، بعد اللصق وقبل الضغط. كل يوم يضيع فيه مبلغ بسبب عنوان خاطئ.</li>
</ul>

<h2>الأسئلة المتكررة حول الأسعار</h2>
<p><strong>«لماذا سعر الصراف أعلى من السعر الرسمي؟»</strong> لأن العرض والطلب في السوق الموازية يحددان سعر الدينار الحقيقي للتحويلات، والسعر الرسمي سعر وهمي لم يتغير منذ سنوات — الفرق هو هامش الصراف وحق سيولته.</p>
<p><strong>«هل تتطابق أسعاركم مع المنصات العالمية؟»</strong> نعم، المصدر CoinGecko نفسه الذي تجده في مواقع الأسعار الكبرى، والحقن آلي لحظة النشر — أي فروقات صغيرة هي فروق توقيت لا أكثر.</p>
<p><strong>«هل أستعمل هذا التقرير للشراء/البيع؟»</strong> التقرير لأغراض إخبارية وتعليمية حول أدوات نقل الأموال. المضاربة خارج نطاق الموقع، وخارج مصلحة القارئ الجزائري عمومًا.</p>

<div class="cta-redotpay">
  <div>
    <h3>هل تريد بطاقة تدفع بها أونلاين من الجزائر؟</h3>
    <p>بطاقة RedotPay المرتبطة بمحفظة USDT هي الحل العملي الأكثر استعمالًا — الدليل الكامل خطوة بخطوة.</p>
  </div>
  <a class="btn btn-primary" data-cta="redotpay" href="redotpay-guide.html">اقرأ دليل RedotPay</a>
</div>

<div class="ad-slot"></div>
"""
    return html


def inject_report(path: Path, html: str, now: datetime) -> bool:
    """استبدال المحتوى بين العلامتين + تحديث التاريخ في id=report-date."""
    text = path.read_text(encoding="utf-8")
    if START_MARK not in text or END_MARK not in text:
        print(f"⚠ لم يُعثر على علامات التقرير في {path} — تخطي")
        return False
    pattern = re.compile(re.escape(START_MARK) + r".*?" + re.escape(END_MARK), re.DOTALL)
    new_text = pattern.sub(START_MARK + "\n" + html + "\n  " + END_MARK, text, count=1)

    # تحديث التاريخ في رأس الصفحة إن وُجد
    new_text = re.sub(r'(<span id="report-date">)[^<]*(</span>)',
                      r'\g<1>' + now.strftime("%Y/%m/%d %H:%M UTC") + r'\g<2>',
                      new_text, count=1)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def update_archive_date(path: Path, now: datetime) -> bool:
    """تحديث عبارة «آخر تحديث» في صفحة كل المقالات إن وُجدت."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r'(<span id="archive-updated">)[^<]*(</span>)', text)
    if not m:
        return False
    new_text = re.sub(r'(<span id="archive-updated">)[^<]*(</span>)',
                      r'\g<1>' + now.strftime("%Y/%m/%d") + r'\g<2>', text, count=1)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main():
    print("=== كريبتو جازاير — الناشر الآلي ===")
    now = datetime.utcnow()

    # 1) جلب البيانات (إن فشل شيء، لا نمس الصفحات إطلاقًا)
    try:
        prices = fetch_prices()
        dzd = fetch_dzd()
    except Exception as e:
        print(f"✗ فشل جلب البيانات: {e}")
        print("  → الأثر: لا شيء. الصفحات تبقى بآخر نسخة صالحة.")
        sys.exit(1)

    if not prices:
        print("✗ لا أسعار في الاستجابة — إيقاف دون تعديل.")
        sys.exit(1)

    print(f"✓ جلب {len(prices)} أسعار + سعر DZD = {dzd}")
    for r in prices:
        print(f"   {r['id']:12s} ${fmt_usd(r['usd']):>10s}  {r['chg']:+.2f}%")

    # 2) بناء وحقن التقرير
    html = build_report_html(prices, dzd, now)
    if not REPORT.exists():
        print(f"✗ {REPORT} غير موجود")
        sys.exit(1)
    if inject_report(REPORT, html, now):
        print(f"✓ حُدِّث تقرير الأسعار → {REPORT.name}")
    else:
        print("⚠ لم يتغير محتوى التقرير (نفس الأرقام تقريبًا)")

    # 3) تحديث تاريخ الأرشيف إن وُجد
    if ARCHIVE.exists() and update_archive_date(ARCHIVE, now):
        print("✓ حُدِّث تاريخ صفحة المقالات")

    print("=== تم ===")


if __name__ == "__main__":
    main()
