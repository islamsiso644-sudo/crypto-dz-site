/* ===== كريبتو جازاير — تفاعلات الموقع ===== */
document.addEventListener('DOMContentLoaded', function () {

  /* قائمة الجوال */
  var toggle = document.querySelector('.menu-toggle');
  var nav = document.querySelector('.main-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () { nav.classList.toggle('open'); });
  }

  /* السنة في الفوتر */
  var yearEl = document.getElementById('year');
  if (yearEl) { yearEl.textContent = new Date().getFullYear(); }

  /* تحميل الإعدادات: إعلانات A-ADS + روابط العمولة + التحليلات */
  /* المسار يتكيف مع عمق الصفحة (الرئيسية أو داخل مجلد articles/) */
  var depth = location.pathname.indexOf('/articles/') !== -1 ? '../' : '';
  fetch(depth + 'data/config.json')
    .then(function (r) { return r.json(); })
    .then(function (cfg) {
      // 1) حقن كود الإعلانات في كل الخانات
      if (cfg.aads_code) {
        var code = cfg.aads_code.replace(/\\"/g, '"');
        document.querySelectorAll('.ad-slot').forEach(function (slot) {
          slot.classList.add('filled');
          slot.innerHTML = code;
        });
      }
      // 2) تفعيل روابط عمولة RedotPay
      if (cfg.redotpay_affiliate_url) {
        document.querySelectorAll('a[data-cta="redotpay"]').forEach(function (a) {
          a.href = cfg.redotpay_affiliate_url;
          a.target = '_blank';
          a.rel = 'noopener sponsored';
        });
      }
      // 3) تحليلات بلاوينتي (اختياري)
      if (cfg.plausible_domain) {
        var s = document.createElement('script');
        s.src = 'https://plausible.io/js/script.js';
        s.setAttribute('data-domain', cfg.plausible_domain);
        s.defer = true;
        document.head.appendChild(s);
      }
    })
    .catch(function () { /* لا مشكلة إذا لم يوجد الملف */ });

  /* أسعار حية في الصفحة الرئيسية (CoinGecko) */
  var ticker = document.getElementById('live-ticker');
  if (ticker) {
    fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,tether,binancecoin,solana&vs_currencies=usd&include_24hr_change=true')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var names = { bitcoin: ['بيتكوين', '₿'], ethereum: ['إيثيريوم', 'Ξ'], tether: ['تيثر USDT', '₮'], binancecoin: ['بينانس BNB', 'B'], solana: ['سولانا', 'S'] };
        var html = '';
        Object.keys(names).forEach(function (id) {
          if (!data[id]) return;
          var usd = data[id].usd;
          var ch = data[id].usd_24h_change || 0;
          var cls = ch >= 0 ? 'up' : 'down';
          var arrow = ch >= 0 ? '▲' : '▼';
          html += '<div class="ticker-row"><span class="coin">' + names[id][1] + ' ' + names[id][0] +
                  '</span><span><span class="price">$' + usd.toLocaleString('en-US', { maximumFractionDigits: usd < 5 ? 4 : 0 }) +
                  '</span> <span class="' + cls + '" style="font-size:13px">' + arrow + ' ' + Math.abs(ch).toFixed(2) + '%</span></span></div>';
        });
        ticker.innerHTML = html + '<div class="ticker-note">⚡ تحديث مباشر كل زيارة — المصدر: CoinGecko</div>';
      })
      .catch(function () {
        ticker.innerHTML = '<div class="ticker-note">تعذر جلب الأسعار الآن، راجع صفحة تقارير الأسعار اليومية.</div>';
      });
  }
});
