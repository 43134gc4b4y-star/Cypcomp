// "Wanted": products with a price on one side only. Tapping Add price fills the form
// and opens the camera, so a shopper standing at the shelf can add it in seconds.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var W = null, need = "S", brand = "", shown = 30;
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function fold(s) { return String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ı/g, "i"); }
  function tl(v) { return v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " ₺"; }

  var UNITS = /^(ml|g|gr|kg|lt|l|cl|li|lu|adet|x)$/;
  function nice(name) {                 // "NIVEA BODY MILK 400ML." -> "Nivea Body Milk 400 ml"
    var n = String(name).replace(/\s+/g, " ").replace(/[.\-]+$/, "").trim();
    if (/[a-zçğıöşü]/.test(n)) return n;
    return n.replace(/İ/g, "i").toLowerCase().replace(/(\d)(ml|gr|g|kg|lt|l|cl)\b/g, "$1 $2").split(" ").map(function (w) {
      return UNITS.test(w) || /^\d/.test(w) ? w : w.charAt(0).toUpperCase() + w.slice(1);
    }).join(" ");
  }
  var CAM = '<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h3l2-3h6l2 3h3v11H4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><circle cx="12" cy="13" r="3.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>';

  function rows() {
    var list = need === "S" ? W.need_south : W.need_north, q = fold($("wq").value).trim();
    return list.filter(function (r) {
      return (!brand || r.brand === brand) && (!q || fold(r.name + " " + r.brand).indexOf(q) >= 0);
    });
  }

  function draw() {
    var list = need === "S" ? W.need_south : W.need_north, counts = {};
    list.forEach(function (r) { counts[r.brand] = (counts[r.brand] || 0) + 1; });
    $("wbrands").innerHTML = [""].concat(Object.keys(counts)).map(function (b) {
      return '<button type="button" class="' + (b === brand ? "on" : "") + '" data-b="' + esc(b) + '">' +
        (b ? esc(b) + " (" + counts[b] + ")" : "All brands") + "</button>";
    }).join("");
    var r = rows(), other = need === "S" ? "N" : "S", last = "", html = "";
    r.slice(0, shown).forEach(function (w, i) {
      if (w.brand !== last && !brand) { html += '<li class="wbrand">' + esc(w.brand) + "</li>"; last = w.brand; }
      html += '<li class="witem"><div class="wtxt"><div class="wn">' + esc(nice(w.name)) + '</div><div class="wm"><span class="wsize">' + esc(w.size) +
        '</span><span class="whave ' + other + '">' + (other === "N" ? "North" : "South") + " €" + w.eur.toFixed(2) + "</span>" +
        '<span class="wshop">' + esc(w.store.split("|")[0].trim()) + '</span></div></div><button type="button" class="wadd ' + need +
        '" data-i="' + i + '" aria-label="Add the ' + (need === "S" ? "South" : "North") + " price for " + esc(nice(w.name)) + '">' + CAM + "<span>Add</span></button></li>";
    });
    $("wlist").innerHTML = html || '<li class="wnone">Nothing matches that filter. Try a brand name.</li>';
    $("wmore").hidden = r.length <= shown;
    $("wmore").textContent = "Show more (" + (r.length - shown) + " left)";
  }

  fetch("data/wanted.json", { cache: "no-cache" }).then(function (x) { return x.json(); }).then(function (d) {
    W = d;
    $("wcS").textContent = d.need_south.length;
    $("wcN").textContent = d.need_north.length;
    $("wbCount").textContent = d.need_south.length + d.need_north.length;
    draw();
  }).catch(function () { $("wlist").innerHTML = '<li class="wnone">The list didn\u2019t load. Check your connection and try again.</li>'; });

  document.querySelector(".wtabs").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    need = b.getAttribute("data-need"); brand = ""; shown = 30;
    Array.prototype.forEach.call(this.children, function (c) { c.classList.toggle("on", c === b); });
    draw();
  });
  $("wbrands").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    brand = b.getAttribute("data-b"); shown = 30; draw();
  });
  $("wq").addEventListener("input", function () { shown = 30; draw(); });
  $("wmore").addEventListener("click", function () { shown += 30; draw(); });
  $("wlist").addEventListener("click", function (e) {
    var b = e.target.closest("button.wadd"); if (!b) return;
    var w = rows()[+b.getAttribute("data-i")];
    if (w && window.CC_prefill) window.CC_prefill({ need: need, name: nice(w.name), size: w.size, barcode: w.barcode }, true);
  });
})();
