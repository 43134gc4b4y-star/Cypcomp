// "Wanted": products with a price on one side only. Tapping Add price fills the form
// and opens the camera, so a shopper standing at the shelf can add it in seconds.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var W = null, need = "S", brand = "", shown = 30;
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function fold(s) { return String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ı/g, "i"); }
  function tl(v) { return v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " ₺"; }

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
    var r = rows(), other = need === "S" ? "North" : "South";
    $("wlist").innerHTML = r.slice(0, shown).map(function (w, i) {
      return '<li><div class="wtxt"><div class="wn">' + esc(w.name) + '</div><div class="wm">' + esc(w.size) + ". " + other + ": €" +
        w.eur.toFixed(2) + " (" + tl(w.try) + ") at " + esc(w.store) + '</div></div><button type="button" class="wadd ' + need +
        '" data-i="' + i + '">Add price</button></li>';
    }).join("") || '<li class="wnone">Nothing matches that filter.</li>';
    $("wmore").hidden = r.length <= shown;
    $("wmore").textContent = "Show more (" + (r.length - shown) + " left)";
  }

  fetch("data/wanted.json", { cache: "no-cache" }).then(function (x) { return x.json(); }).then(function (d) {
    W = d;
    $("wcS").textContent = "(" + d.need_south.length + ")";
    $("wcN").textContent = "(" + d.need_north.length + ")";
    draw();
  }).catch(function () { $("wanted").hidden = true; });

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
    if (w && window.CC_prefill) window.CC_prefill({ need: need, name: w.name, size: w.size, barcode: w.barcode }, true);
  });
})();
