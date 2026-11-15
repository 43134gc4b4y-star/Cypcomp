// A short animated welcome for each of the three pages. Shown once per page every time the site
// is opened; the "?" button at the top brings it back.
(function () {
  "use strict";
  var TAGS = '<div class="ia ia-prices" aria-hidden="true"><div class="it itN"><i>North</i><b>€2.40</b></div>' +
    '<div class="it itS"><i>South</i><b>€1.65</b><em>€0.75 less</em></div></div>';
  var WANT = '<div class="ia ia-wanted" aria-hidden="true"><div class="it itN"><i>North</i><b>€3.10</b></div>' +
    '<div class="it itQ"><i>South</i><b>?</b></div><svg class="lens" width="54" height="54" viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="M15.5 15.5l5 5" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg></div>';
  var ADD = '<div class="ia ia-add" aria-hidden="true"><div class="bars"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><i class="scan"></i></div><div class="typed">€1.99</div></div>';
  var PAGES = {
    prices: { art: TAGS, h: "One island, two price tags",
      p: "Every morning we check supermarket prices in the North and the South and put the same products side by side. The cheaper side is coloured in, with the saving in yellow.",
      b: "Start comparing" },
    wanted: { art: WANT, h: "Help fill the gaps",
      p: "These products have a price on one side of the island only. Spot one in a shop, tap Add, and it joins the comparison.",
      b: "Show me the list" },
    contrib: { art: ADD, h: "Add a price in seconds",
      p: "Scan or photograph the barcode, then type the shelf price and the shop. Every price is checked before it appears on the site.",
      b: "Got it" }
  };
  var box = document.createElement("div");
  box.className = "intro"; box.hidden = true;
  box.innerHTML = '<div class="intro-card" role="dialog" aria-modal="true" aria-labelledby="introH"><div id="introArt"></div><h2 id="introH"></h2><p id="introP"></p><button type="button" class="main" id="introB"></button></div>';
  document.body.appendChild(box);
  var last = null;

  function seen(v) { try { return sessionStorage.getItem("cc-intro-" + v) === "1"; } catch (e) { return false; } }
  function mark(v) { try { sessionStorage.setItem("cc-intro-" + v, "1"); } catch (e) { /* private mode: shows again next time */ } }
  function view() { var v = (location.hash || "").slice(1); return PAGES[v] ? v : "prices"; }

  function open(v) {
    var pg = PAGES[v];
    document.getElementById("introArt").innerHTML = pg.art;
    document.getElementById("introH").textContent = pg.h;
    document.getElementById("introP").textContent = pg.p;
    document.getElementById("introB").textContent = pg.b;
    last = document.activeElement;
    box.hidden = false;
    requestAnimationFrame(function () { box.classList.add("show"); document.getElementById("introB").focus(); });
    mark(v);
  }
  function close() {
    box.classList.remove("show");
    setTimeout(function () { box.hidden = true; if (last && last.focus) last.focus(); }, 220);
  }
  function maybe() { var v = view(); if (!seen(v) && box.hidden) setTimeout(function () { if (view() === v) open(v); }, 350); }

  document.getElementById("introB").addEventListener("click", close);
  box.addEventListener("click", function (e) { if (e.target === box) close(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !box.hidden) close(); });
  var help = document.getElementById("helpBtn");
  if (help) help.addEventListener("click", function () { open(view()); });
  window.addEventListener("hashchange", maybe);
  maybe();
})();
