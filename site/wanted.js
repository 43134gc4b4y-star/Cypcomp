// "Wanted": products with a price on one side only. Tapping Add price fills the form
// and opens the camera, so a shopper standing at the shelf can add it in seconds.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var W = null, need = "S", brand = "", shown = 30;
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function fold(s) { return String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ı/g, "i"); }
  function num(v) { return Number(v).toLocaleString("en-GB"); }
  function daysSince(d) { return W ? Math.round((Date.parse(W.updated) - Date.parse(d)) / 864e5) : 99; }
  function isNew(r) { return r.since && daysSince(r.since) <= 7; }
  var SEEN = "cc-wanted-seen";
  function lastVisit() { try { return localStorage.getItem(SEEN) || ""; } catch (e) { return ""; } }
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
      html += '<li class="witem"><div class="wtxt"><div class="wn">' + (isNew(w) ? '<span class="wnew">New</span>' : "") + esc(nice(w.name)) +
        '</div><div class="wm"><span class="wsize">' + esc(w.size) +
        '</span><span class="whave ' + other + '">' + (other === "N" ? "North" : "South") + " €" + w.eur.toFixed(2) + "</span>" +
        '<span class="wshop">' + (w.shops > 1 ? "In " + w.shops + " shops" : esc(w.store.split("|")[0].trim())) + '</span></div></div><button type="button" class="wadd ' + need +
        '" data-i="' + i + '" aria-label="Add the ' + (need === "S" ? "South" : "North") + " price for " + esc(nice(w.name)) + '">' + CAM + "<span>Add</span></button></li>";
    });
    $("wlist").innerHTML = html || '<li class="wnone">Nothing matches that filter. Try a brand name.</li>';
    var total = need === "S" ? W.counts.need_south : W.counts.need_north;
    $("wnote").textContent = total > list.length ? "The " + num(list.length) + " most wanted of " + num(total) + ". Products sold in more shops come first." :
      "Products sold in more shops come first.";
    $("wmore").hidden = r.length <= shown;
    $("wmore").textContent = "Show more (" + (r.length - shown) + " left)";
  }

  fetch("data/wanted.json", { cache: "no-cache" }).then(function (x) { return x.json(); }).then(function (d) {
    W = d;
    $("wcS").textContent = num(d.counts.need_south);
    $("wcN").textContent = num(d.counts.need_north);
    // the tab's badge counts products new to the list since this phone last opened Wanted (or this week)
    var since = lastVisit(), fresh = d.need_south.concat(d.need_north).filter(function (r) {
      return since ? r.since > since : isNew(r);
    }).length;
    $("wbCount").textContent = fresh ? (fresh > 99 ? "99+" : fresh) + " new" : "";
    drawFound();
    draw();
    if (location.hash === "#wanted") markSeen();
  }).catch(function () { $("wlist").innerHTML = '<li class="wnone">The list didn\u2019t load. Check your connection and try again.</li>'; });

  function markSeen() {
    try { localStorage.setItem(SEEN, W.updated); } catch (e) { /* private mode */ }
    $("wbCount").textContent = "";
  }
  window.addEventListener("hashchange", function () { if (W && location.hash === "#wanted") markSeen(); });

  // products that left the list because a price was found for the other side
  function drawFound() {
    var f = (W.found || []).filter(function (x) { return daysSince(x.date) <= 30; });
    if (!f.length) { $("wfound").hidden = true; return; }
    $("wfound").hidden = false;
    $("wfound").innerHTML = '<h3><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>' +
      num(f.length) + " found in the last 30 days</h3><p>These now have prices on both sides.</p><ul>" + f.slice(0, 5).map(function (x) {
        return '<li><a href="#item=' + encodeURIComponent(x.id) + '">' + esc(nice(x.name)) + "</a><span>" + (x.need === "S" ? "South" : "North") + " price found</span></li>";
      }).join("") + "</ul>";
  }

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
