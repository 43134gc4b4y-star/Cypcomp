// Compare Cyprus – reads data/prices.json (written by the daily scraper) and shows it.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var DATA = null, query = "", cat = "", shown = 40, sortBy = "eur", kindF = "";
  // "My list": products the shopper saved on this phone (kept in this browser only)
  var MYKEY = "cc-mylist", mine = [];
  try { mine = JSON.parse(localStorage.getItem(MYKEY) || "[]") || []; } catch (e) { mine = []; }
  function isMine(id) { return mine.indexOf(id) >= 0; }
  function toggleMine(id) {
    var i = mine.indexOf(id);
    if (i >= 0) mine.splice(i, 1); else mine.push(id);
    saveMine();
  }
  function saveMine() {
    try { localStorage.setItem(MYKEY, JSON.stringify(mine)); } catch (e) { /* private mode: kept until the page closes */ }
    drawMine();
  }
  var STAR = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M12 3.2l2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 17l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z"/></svg>';
  function sameKind(it) { return it.kind !== "generic"; }

  var TRENDING = [];
  // English search words -> Turkish/Greek words shops use, so "milk" also finds "süt"
  var ALIAS = {
    milk: ["sut", "gala", "fresh milk"], coffee: ["kahve", "nescafe", "instant coffee"], tea: ["cay", "lipton", "twinings"],
    honey: ["bal"], eggs: ["yumurta", "avga"], egg: ["eggs"], cheese: ["peynir", "cheddar", "feta", "edam"],
    halloumi: ["hellim"], water: ["su", "still water", "sparkling water"], butter: ["tereyagi", "tereyag"],
    yoghurt: ["yogurt"], yogurt: ["yoghurt"],
    nappies: ["bebek bezi", "pampers", "diapers", "molfix", "huggies"], "baby milk": ["baby formula", "aptamil", "bebelac", "nan"],
    tissue: ["mendil", "tissues", "selpak", "kleenex", "toilet paper"], "toilet paper": ["tuvalet kagidi"],
    cola: ["coca cola", "pepsi", "kola"], "protein bar": ["protein"], chocolate: ["cikolata", "chocolate bar"],
    rice: ["pirinc"], pasta: ["makarna", "spaghetti", "penne"], sugar: ["seker"], flour: ["un"],
    "olive oil": ["zeytinyagi", "zeytinyag"], tomatoes: ["domates", "tomato"], potatoes: ["patates"],
    shampoo: ["sampuan"], detergent: ["deterjan", "laundry"], toothpaste: ["dis macunu"], soap: ["sabun"],
    beer: ["bira"], crisps: ["cips", "chips", "pringles", "lays"], cereal: ["corn flakes", "gevrek"],
    "cat food": ["kedi", "whiskas", "felix"], "dog food": ["kopek", "pedigree"], deodorant: ["deo", "roll on"]
  };
  var TRENDING_CANDIDATES = ["milk", "coffee", "cola", "eggs", "halloumi", "cheese", "butter", "chocolate", "crisps",
    "shampoo", "deodorant", "baby milk", "nappies", "tissue", "olive oil", "cereal", "cat food", "honey", "tea", "water"];
  // picture shown only if a product photo fails to load: first match on the product name, then the category
  var CAT_ICON = [[/mince|beef|steak|lamb|pork|sausage|frankfurter|ham\b/i, "🥩"], [/chicken|turkey/i, "🍗"], [/tomato(es)?$|^tomato/i, "🍅"],
    [/potatoes|^potato/i, "🥔"], [/cucumber/i, "🥒"], [/egg/i, "🥚"], [/cheese|halloumi|cheddar/i, "🧀"], [/butter|margarine/i, "🧈"],
    [/toothpaste|toothbrush|mouthwash/i, "🪥"], [/razor|shav|gillette|mach3/i, "🪒"], [/baby|formula|napp|diaper/i, "🍼"],
    [/coffee|nescaf/i, "☕"], [/\btea\b/i, "🍵"], [/juice|nectar/i, "🧃"], [/water/i, "💧"], [/cola|pepsi|fanta|sprite|drink|energy/i, "🥤"],
    [/milk|yog/i, "🥛"], [/chocolate|cocoa/i, "🍫"], [/crisps|chips|pringles|doritos/i, "🍿"], [/biscuit|cookie|wafer|cracker/i, "🍪"],
    [/pasta|spaghetti|penne|barilla/i, "🍝"], [/rice|bulgur|chickpea|lentil/i, "🍚"], [/oil\b/i, "🫒"], [/tuna|fish|salmon/i, "🐟"],
    [/bread|toast|flour/i, "🍞"], [/cereal|corn flakes|oats|porridge|weetabix/i, "🥣"], [/pizza/i, "🍕"], [/ice cream/i, "🍨"], [/honey/i, "🍯"],
    [/almond|nut/i, "🥜"], [/ketchup|mayonnaise|sauce|paste|pesto|mustard/i, "🥫"], [/soap|shower|bath/i, "🧼"],
    [/pads|tissue|paper|wipes/i, "🧻"], [/cleaner|softener|detergent|drain|bleach|dettol|fairy|finish/i, "🧽"], [/cat food|dog food|whiskas|pet/i, "🐾"],
    [/shampoo|conditioner|lotion|cream|deodor|spray|sun|nivea|dove|axe/i, "🧴"], [/fruit|veg/i, "🥬"], [/snack|sweet/i, "🍬"]];

  function fold(s) {
    return (s || "").toLowerCase().replace(/ı/g, "i").replace(/ş/g, "s").replace(/ğ/g, "g").replace(/ç/g, "c").replace(/ö/g, "o").replace(/ü/g, "u")
      .normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function eur(v) { return "€" + v.toFixed(2); }
  function tl(v) { return v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " ₺"; }
  function safeUrl(u) { return /^https?:\/\//i.test(u || "") ? u : ""; }
  function icon(it) {
    var i;
    for (i = 0; i < CAT_ICON.length; i++) if (CAT_ICON[i][0].test(it.name)) return CAT_ICON[i][1];
    for (i = 0; i < CAT_ICON.length; i++) if (CAT_ICON[i][0].test(it.category || "")) return CAT_ICON[i][1];
    return "🛒";
  }

  // a handful of plain categories instead of every shop's own shelf names
  var GROUPS = [
    ["Baby", "👶", /baby|bebek/i],
    ["Personal care", "🧴", /personal|deodor|body|shav|hand cream|mouthwash|toothpaste|sunscreen|conditioner|skincare|bath|shower|hair|intimate/i],
    ["Household", "🧽", /clean|laundry|household|paper|pets?$|detergent/i],
    ["Drinks", "🥤", /drinks?|coffee|tea$|juice|water|beer|wine/i],
    ["Dairy & eggs", "🥛", /milk|dairy|cheese|egg|yog/i],
    ["Snacks & sweets", "🍫", /snack|cookie|cracker|wafer|chocolate|sweet|biscuit|crisps/i],
    ["Fresh & frozen", "🥩", /cold cuts|fruit|veg|frozen|meat|fish/i],
    ["Food cupboard", "🥫", /./]
  ];
  function groupOf(it) { for (var i = 0; i < GROUPS.length; i++) if (GROUPS[i][2].test(it.category || "")) return GROUPS[i][0]; return "Food cupboard"; }

  function words(t) { return fold(t).split(/[^a-z0-9]+/).filter(Boolean); }

  function index(it) {
    it._n = words(it.name); it.group = groupOf(it);
    var all = [it.name, it.category, it.unit];
    it.north.concat(it.south).forEach(function (o) { all.push(o.name, o.store, o.shelf ? o.shelf.name : ""); });
    it._a = words(all.join(" "));
  }

  // a query word matches a whole word, or the start of a longer word (5+ letters typed)
  function hasWord(list, w) {
    for (var i = 0; i < list.length; i++) if (list[i] === w || (w.length >= 5 && list[i].indexOf(w) === 0)) return true;
    return false;
  }

  function phraseScore(it, phrase) {
    var ws = words(phrase);
    if (!ws.length) return 0;
    if (ws.every(function (w) { return hasWord(it._n, w); })) return it.kind === "generic" && !/pack sizes/.test(it.unit) ? 3.5 : 3;   // own name; "any brand" items first
    if (ws.every(function (w) { return hasWord(it._a, w); })) return 1;   // only in a shop's product name
    return 0;
  }

  function score(it, q) {
    if (!q) return 1;
    var best = phraseScore(it, q);
    (ALIAS[q.trim()] || []).forEach(function (a) { best = Math.max(best, phraseScore(it, a) - 0.5); });
    return best;
  }

  // money saved on one pack: difference between the cheapest shelf price on each side (in €)
  function shelfEur(o) { return o ? (o.shelf ? o.shelf.eur : o.eur) : 0; }
  function gap(it) { return Math.abs(shelfEur(it.north[0]) - shelfEur(it.south[0])); }

  function perLabel(it) {
    var m = /price (per [^·]+)/.exec(it.unit || "");
    return m ? m[1].trim().replace(/^per 1 l$/, "per litre").replace(/^per 1 kg$/, "per kg").replace(/^per 1 /, "per ") : "";
  }

  function side(label, cls, o, win, it) {
    // one half of the price label; the cheaper half is filled with its side's colour and carries the saving
    var e = o.shelf ? o.shelf.eur : o.eur, t = o.shelf ? o.shelf.try : o.try;
    var sticker = win ? '<div class="sticker"><b>' + eur(gap(it)) + " less</b><span>" + Math.round(it.saving_pct) + "% cheaper</span></div>" : "";
    return '<div class="tag ' + cls + (win ? " win" : "") + '"><div class="strip">' + label + (win ? " is cheaper" : "") + '</div><div class="pr">' + eur(e) +
      '</div><div class="pl">' + tl(t) + "</div>" + sticker + '<div class="sn">' + esc(o.store.split("|")[0].trim()) + "</div></div>";
  }

  function where(label, cls, o, per) {
    // the full story for one side, shown when the card is opened
    var links = "";
    if (safeUrl(o.maps)) links += '<a target="_blank" rel="noopener" href="' + esc(o.maps) + '">Map</a>';
    if (safeUrl(o.url)) links += '<a target="_blank" rel="noopener" href="' + esc(o.url) + '">Shop page</a>';
    var unit = o.shelf && per ? "<div>" + eur(o.eur) + " " + esc(per) + "</div>" : "";
    return '<div class="wh ' + cls + '"><b class="' + (cls === "N" ? "tN" : "tS") + '">' + label + "</b><div class=\"sn\">" + esc(o.store) + "</div>" +
      (o.town ? "<div>" + esc(o.town) + "</div>" : "") + '<div class="pn">' + esc(nice(o.shelf ? o.shelf.name : o.name)) + "</div>" + unit +
      (links ? '<div class="links">' + links + "</div>" : "") + "</div>";
  }

  function nice(name) {                 // shout-case words to Title case: "GILLETTE MACH3 4LU" -> "Gillette Mach3 4lu"
    var n = String(name).replace(/\s+/g, " ").trim();
    return n.split(" ").map(function (w) {
      if (!/[A-ZÇĞİÖŞÜ]{2}/.test(w) || /[a-zçğıöşü]/.test(w)) return w;          // already mixed case, or not a word
      var l = w.replace(/İ/g, "i").toLowerCase();
      if (/^\d/.test(l)) return l.replace(/^(\d+(?:[.,]\d+)?)(ml|gr|g|kg|lt|l|cl)$/, "$1 $2");
      if (/^(ml|gr|g|kg|lt|cl|pcs)$/.test(l)) return l;
      return l.replace(/(^|[(&\-\/])([a-zçğıöşü])/g, function (m, a, c) { return a + c.toUpperCase(); });
    }).join(" ");
  }


  function others(list) {
    return list.slice(1).map(function (o) {
      var nm = safeUrl(o.url) ? '<a target="_blank" rel="noopener" href="' + esc(o.url) + '">' + esc(o.store.split("|")[0].trim()) + "</a>" : esc(o.store.split("|")[0].trim());
      return "<div><span>" + nm + "</span><b>" + eur(o.shelf ? o.shelf.eur : o.eur) + "</b></div>";
    }).join("");
  }

  function card(it) {
    var n = it.north[0], s = it.south[0], per = perLabel(it);
    var img = safeUrl(it.image) ? '<div class="art"><img loading="lazy" decoding="async" alt="" src="' + esc(it.image) +
      '" onerror="this.parentNode.className=\'art noimg\';this.replaceWith(document.createTextNode(\'' + icon(it) + '\'))"></div>' :
      '<div class="art noimg">' + icon(it) + "</div>";
    var verdict = it.cheaper === "=" ? '<div class="verdict same">Same price on both sides</div>' : "";
    var chains = ["Lidl", "AlphaMega"].map(function (c) {
      var o = it.south.filter(function (x) { return x.store === c; })[0];
      return o && o !== s ? "<b>" + c + "</b> " + eur(o.shelf ? o.shelf.eur : o.eur) : "";
    }).filter(Boolean).join(", ");
    var total = it.north.length + it.south.length;
    var href = "#item=" + encodeURIComponent(it.id);
    var on = isMine(it.id);
    return '<article class="item" data-href="' + href + '"><button type="button" class="star' + (on ? " on" : "") + '" data-id="' + esc(it.id) + '" aria-pressed="' + on +
      '" aria-label="' + (on ? "Remove from" : "Add to") + ' my list">' + STAR + '</button><a class="head" href="' + href + '">' + img + '<div class="ttl"><h3 class="name">' + esc(nice(it.name)) +
      '</h3><div class="unit">' + esc([it.unit, it.category].filter(Boolean).join(" · ")) + "</div>" + kindPill(it) + '</div></a><div class="tags">' +
      side("North", "N", n, it.cheaper === "N", it) + side("South", "S", s, it.cheaper === "S", it) + "</div>" + verdict +
      (chains ? '<div class="chains">Also in the <span class="tS">South</span>: ' + chains + "</div>" : "") +
      '<a class="seeall" href="' + href + '">See all ' + total + " prices and shops</a></article>";
  }

  function kindPill(it) {
    return sameKind(it) ? '<span class="kind same" title="Same brand and pack size on both sides">✓ Same product</span>' :
      '<span class="kind any" title="Cheapest of any brand, same pack size">Any brand</span>';
  }

  // ---- product page: everything about one product, opened by tapping its card ----
  function sheet(it) {
    var rows = [];
    it.north.forEach(function (o) { rows.push({ o: o, side: "N" }); });
    it.south.forEach(function (o) { rows.push({ o: o, side: "S" }); });
    var price = function (r) { return r.o.shelf ? r.o.shelf.eur : r.o.eur; };
    var lira = function (r) { return r.o.shelf ? r.o.shelf.try : r.o.try; };
    rows.sort(function (a, b) { return price(a) - price(b); });
    var max = Math.max.apply(null, rows.map(price)) || 1, per = perLabel(it);
    var img = safeUrl(it.image) ? '<img alt="" src="' + esc(it.image) + '" onerror="this.replaceWith(document.createTextNode(\'' + icon(it) + '\'))">' : icon(it);
    var win = it.cheaper === "N" ? "North" : "South";
    var banner = it.cheaper === "=" ? '<div class="pv same">Same price on both sides</div>' :
      '<div class="pv ' + it.cheaper + '"><span>Cheaper in the ' + win + "</span><b>" + eur(gap(it)) + " less</b><span>" + Math.round(it.saving_pct) + "% cheaper</span></div>";
    var best = { N: it.north[0], S: it.south[0] };
    var duo = ["N", "S"].map(function (k) {
      var o = best[k];
      return '<div class="pd ' + k + (it.cheaper === k ? " win" : "") + '"><i>' + (k === "N" ? "North" : "South") + "</i><b>" + eur(o.shelf ? o.shelf.eur : o.eur) +
        "</b><span>" + tl(o.shelf ? o.shelf.try : o.try) + "</span></div>";
    }).join("");
    var list = rows.map(function (r, i) {
      var o = r.o, links = "";
      if (safeUrl(o.maps)) links += '<a target="_blank" rel="noopener" href="' + esc(o.maps) + '">Map</a>';
      if (safeUrl(o.url)) links += '<a target="_blank" rel="noopener" href="' + esc(o.url) + '">Shop page</a>';
      var pname = nice(o.shelf ? o.shelf.name : o.name);
      return '<li class="pr-row ' + r.side + '"><div class="prt"><span class="chip ' + r.side + '">' + (r.side === "N" ? "North" : "South") + "</span>" +
        (i === 0 ? '<span class="chip best">Cheapest</span>' : "") + '<b class="pp">' + eur(price(r)) + '</b></div><div class="prs">' + esc(o.store.split("|")[0].trim()) +
        '<span class="ptl">' + tl(lira(r)) + '</span></div><div class="pbar"><span style="width:' + Math.max(6, Math.round(100 * price(r) / max)) + '%"></span></div>' +
        '<div class="pmeta">' + esc([o.town, pname].filter(Boolean).join(" · ")) + (o.shelf && per ? " · " + eur(o.eur) + " " + esc(per) : "") + "</div>" +
        (links ? '<div class="links">' + links + "</div>" : "") + "</li>";
    }).join("");
    var note = it.kind !== "exact" && it.note ? '<p class="note">' + esc(it.note) + "</p>" : "";
    var cheaper = '<div class="pscan"><h3>Seen it cheaper?</h3><p>Scan here and we will add it to the site.</p>' +
      '<button type="button" class="pscanb" id="pscan"><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true">' +
      '<path d="M3 8V5a2 2 0 0 1 2-2h3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3M7 8v8M10.5 8v8M14 8v8M17 8v8"/></svg>Scan the barcode</button></div>';
    var share = navigator.share ? '<button type="button" class="main ghost" id="pshare">Share this comparison</button>' : "";
    return '<div class="psheet-in" role="dialog" aria-modal="true" aria-labelledby="ptitle"><button type="button" class="pclose" id="pclose" aria-label="Close">✕</button>' +
      '<div class="phero"><div class="pimg">' + img + '</div><h2 id="ptitle">' + esc(nice(it.name)) + '</h2><div class="unit">' +
      esc([it.unit, it.category].filter(Boolean).join(" · ")) + "</div>" + kindPill(it) + "</div>" + '<div class="pduo">' + duo + "</div>" + banner +
      '<button type="button" class="psave' + (isMine(it.id) ? " on" : "") + '" id="psave" data-id="' + esc(it.id) + '">' + STAR + "<span>" +
      (isMine(it.id) ? "On my list" : "Add to my list") + "</span></button>" + cheaper +
      '<h3 class="ph3">All ' + rows.length + ' prices, cheapest first</h3><ul class="plist">' + list + "</ul>" + note + share + "</div>";
  }

  // drag a pop-up down to close it
  function swipeClose(box, cardOf, canStart, done) {
    var y0 = null, dy = 0, card = box;
    var cardNow = typeof cardOf === "function" ? cardOf : function () { return cardOf; };
    box.addEventListener("touchstart", function (e) {
      y0 = e.touches.length === 1 && canStart() ? e.touches[0].clientY : null; dy = 0;
      card = cardNow() || box;
    }, { passive: true });
    box.addEventListener("touchmove", function (e) {
      if (y0 === null) return;
      dy = e.touches[0].clientY - y0;
      if (dy <= 0 || !canStart()) { dy = 0; card.style.transform = ""; card.style.transition = ""; return; }
      if (e.cancelable) e.preventDefault();
      card.style.transition = "none"; card.style.transform = "translateY(" + dy + "px)";
    }, { passive: false });
    var end = function () {
      if (y0 === null) return;
      y0 = null; card.style.transition = "";
      if (dy > 90) { card.style.transform = "translateY(100%)"; done(); setTimeout(function () { card.style.transform = ""; }, 300); }
      else card.style.transform = "";
      dy = 0;
    };
    box.addEventListener("touchend", end); box.addEventListener("touchcancel", end);
  }
  window.CC_swipe = swipeClose;

  var sheetEl = document.createElement("div");
  sheetEl.className = "psheet"; sheetEl.hidden = true;
  document.body.appendChild(sheetEl);
  function closeSheet() {
    if (sheetEl.hidden) return;
    sheetEl.classList.remove("show"); document.body.classList.remove("noscroll");
    setTimeout(function () { sheetEl.hidden = true; sheetEl.innerHTML = ""; drawMine(); }, 240);
  }
  swipeClose(sheetEl, function () { return sheetEl.firstChild; }, function () { return sheetEl.scrollTop <= 0; },
    function () { if ($("pclose")) $("pclose").click(); });
  function showPanel(html) {
    sheetEl.innerHTML = html; sheetEl.hidden = false; sheetEl.scrollTop = 0;
    document.body.classList.add("noscroll");
    requestAnimationFrame(function () { sheetEl.classList.add("show"); });
    $("pclose").focus({ preventScroll: true });
    $("pclose").onclick = function () { if (history.length > 1 && cameFromList) history.back(); else location.hash = "#prices"; };
  }
  function openSheet(id) {
    var it = DATA && DATA.items.filter(function (x) { return x.id === id; })[0];
    if (!it) return false;
    showPanel(sheet(it));
    $("psave").onclick = function () {
      toggleMine(it.id);
      var on = isMine(it.id);
      this.classList.toggle("on", on); this.lastChild.textContent = on ? "On my list" : "Add to my list";
    };
    $("pscan").onclick = function () {
      if (window.CC_prefill) window.CC_prefill({ name: nice(it.name), size: it.unit, barcode: it.barcode }, true);
      else location.hash = "#contrib";
    };
    if ($("pshare")) $("pshare").onclick = function () {
      navigator.share({ title: nice(it.name) + " – Compare Cyprus", text: nice(it.name) + ": " + (it.cheaper === "=" ? "same price North and South" :
        eur(gap(it)) + " cheaper in the " + (it.cheaper === "N" ? "North" : "South")), url: location.href }).catch(function () {});
    };
    return true;
  }
  // ---- My list: saved products and what the whole basket costs on each side ----
  function shelfEur(o) { return o.shelf ? o.shelf.eur : o.eur; }
  function listPanel() {
    var items = mine.map(function (id) { return DATA.items.filter(function (x) { return x.id === id; })[0]; }).filter(Boolean);
    var gone = mine.length - items.length;
    var tn = 0, ts = 0;
    items.forEach(function (it) { tn += shelfEur(it.north[0]); ts += shelfEur(it.south[0]); });
    var head = '<div class="psheet-in" role="dialog" aria-modal="true" aria-labelledby="ptitle"><button type="button" class="pclose" id="pclose" aria-label="Close">✕</button>' +
      '<div class="phero"><div class="pimg mylogo">' + STAR + '</div><h2 id="ptitle">My list</h2><div class="unit">Saved on this phone · cheapest shop on each side</div></div>';
    if (!items.length) {
      return head + '<div class="mempty"><p>Tap the <b>☆ star</b> on any product to add it here.</p><p>You will see what your whole shop costs in the <span class="tN">North</span> and in the <span class="tS">South</span>.</p></div>' +
        (gone ? '<p class="note">' + gone + " saved item" + (gone > 1 ? "s are" : " is") + " no longer compared.</p>" : "") + "</div>";
    }
    var d = tn - ts, win = d > 0.005 ? "S" : d < -0.005 ? "N" : "=";
    var duo = '<div class="pduo"><div class="pd N' + (win === "N" ? " win" : "") + '"><i>North total</i><b>' + eur(tn) + "</b><span>" + tl(tn * DATA.fx.eur_try) + "</span></div>" +
      '<div class="pd S' + (win === "S" ? " win" : "") + '"><i>South total</i><b>' + eur(ts) + "</b><span>" + tl(ts * DATA.fx.eur_try) + "</span></div></div>";
    var banner = win === "=" ? '<div class="pv same">Same total on both sides</div>' :
      '<div class="pv ' + win + '"><span>Your list is cheaper in the ' + (win === "N" ? "North" : "South") + "</span><b>" + eur(Math.abs(d)) + " less</b><span>" +
      Math.round(Math.abs(d) / Math.max(tn, ts) * 100) + "% cheaper</span></div>";
    var rows = items.map(function (it) {
      var n = shelfEur(it.north[0]), s = shelfEur(it.south[0]);
      return '<li class="mrow"><a href="#item=' + encodeURIComponent(it.id) + '"><b>' + esc(nice(it.name)) + "</b><small>" + esc(it.unit || "") +
        "</small></a><span class=\"mp N" + (it.cheaper === "N" ? " win" : "") + '">' + eur(n) + '</span><span class="mp S' + (it.cheaper === "S" ? " win" : "") + '">' + eur(s) +
        '</span><button type="button" class="mrm" data-id="' + esc(it.id) + '" aria-label="Remove ' + esc(nice(it.name)) + '">✕</button></li>';
    }).join("");
    return head + duo + banner + '<h3 class="ph3">' + items.length + " item" + (items.length > 1 ? "s" : "") + '</h3><div class="mhead"><span></span><span class="tN">North</span><span class="tS">South</span><span></span></div><ul class="mlist">' + rows + "</ul>" +
      (gone ? '<p class="note">' + gone + " saved item" + (gone > 1 ? "s are" : " is") + " no longer compared.</p>" : "") +
      '<button type="button" class="main ghost" id="mclear">Clear my list</button></div>';
  }
  function openList() {
    showPanel(listPanel());
    sheetEl.onclick = function (e) {
      var rm = e.target.closest(".mrm");
      if (rm) { toggleMine(rm.getAttribute("data-id")); var y = sheetEl.scrollTop; openList(); sheetEl.scrollTop = y; render(); return; }
      if (e.target.id === "mclear") { mine = []; saveMine(); openList(); render(); }
    };
  }
  var pill = document.createElement("button");
  pill.type = "button"; pill.className = "mypill"; pill.hidden = true;
  document.body.appendChild(pill);
  pill.onclick = function () { cameFromList = true; location.hash = "#list"; };
  function drawMine() {
    var n = mine.filter(function (id) { return !DATA || DATA.items.some(function (x) { return x.id === id; }); }).length;
    pill.innerHTML = STAR + "<span>My list</span><b>" + n + "</b>";
    pill.hidden = !n || curView !== "prices" || !sheetEl.hidden;
  }

  var cameFromList = false;
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#item="]');
    if (a) cameFromList = true;
    if (e.target === sheetEl) $("pclose").click();
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !sheetEl.hidden) $("pclose").click(); });
  $("out").addEventListener("click", function (e) {          // star on a card
    var b = e.target.closest(".star"); if (!b) return;
    var id = b.getAttribute("data-id"); toggleMine(id);
    var on = isMine(id);
    b.classList.toggle("on", on); b.setAttribute("aria-pressed", on); b.setAttribute("aria-label", (on ? "Remove from" : "Add to") + " my list");
    b.classList.remove("pop"); void b.offsetWidth; b.classList.add("pop");
  });

  function render() {
    var q = fold(query).trim();
    var list = DATA.items.map(function (it) { return { it: it, s: (!cat || it.group === cat) && (!sideF || it.cheaper === sideF) && (!kindF || (kindF === "same") === sameKind(it)) ? score(it, q) : 0 }; })
      .filter(function (x) { return x.s > 0; })
      .sort(function (a, b) {
        var bySaving = sortBy === "pct" ? b.it.saving_pct - a.it.saving_pct :
          sortBy === "az" ? nice(a.it.name).localeCompare(nice(b.it.name)) : gap(b.it) - gap(a.it);
        return b.s - a.s || (q ? a.it.name.length - b.it.name.length : 0) || bySaving;
      })
      .map(function (x) { return x.it; });
    $("listhead").textContent = q ? list.length + (list.length === 1 ? " result" : " results") + " for “" + query + "”" :
      (cat || (kindF === "same" ? "Same product" : kindF === "any" ? "Any brand" : "All products")) + " (" + list.length + ")";
    $("sidef").hidden = !sideF;
    if (sideF) $("sidef").innerHTML = 'Only cheaper in the <b class="' + (sideF === "N" ? "tN" : "tS") + '">' + (sideF === "N" ? "North" : "South") + "</b> <span>✕ Show all</span>";
    Array.prototype.forEach.call(document.querySelectorAll("#stats .sc"), function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-s") === sideF); });
    $("qx").hidden = !query;
    var html = list.slice(0, shown).map(card).join("");
    if (!DATA.items.length) {
      html = '<div class="empty"><div class="name">Prices appear after the first daily run</div><p class="small">The scraper runs every morning and fills this page automatically.</p></div>';
    } else if (!list.length) {
      html = '<div class="empty"><div class="name">' + (query ? "No comparison for “" + esc(query) + "” yet" : "Nothing here yet") + '</div><p class="small">An item shows up once the same product (brand and size) is on sale in both <span class="tN">North</span> and <span class="tS">South</span>. Try a shorter word, such as a brand name.</p></div>';
    }
    $("out").innerHTML = html;
    $("more").hidden = list.length <= shown;
    $("more").textContent = "Show more (" + (list.length - shown) + " left)";
  }

  function chips(el, labels, active, onPick) {
    el.innerHTML = labels.map(function (l) { return '<button type="button" class="' + (l.v === active ? "on" : "") + '" data-v="' + esc(l.v) + '">' + esc(l.t) + "</button>"; }).join("");
    el.onclick = function (e) { var b = e.target.closest("button"); if (b) onPick(b.getAttribute("data-v")); };
  }

  function drawChips() {
    var counts = {};
    DATA.items.forEach(function (i) { counts[i.group] = (counts[i.group] || 0) + 1; });
    var tiles = [["", "🛒", DATA.items.length, "All"]].concat(GROUPS.filter(function (g) { return counts[g[0]]; })
      .map(function (g) { return [g[0], g[1], counts[g[0]], g[0]]; }));
    $("cats").innerHTML = tiles.map(function (t) {
      return '<button type="button" class="cat' + (t[0] === cat && !query ? " on" : "") + '" data-v="' + esc(t[0]) + '" aria-pressed="' + (t[0] === cat && !query) +
        '"><span class="ce" aria-hidden="true">' + t[1] + "</span><span class=\"cl\">" + esc(t[3]) + '</span><span class="cn">' + t[2] + "</span></button>";
    }).join("");
    $("cats").onclick = function (e) {
      var b = e.target.closest("button"); if (!b) return;
      cat = b.getAttribute("data-v"); query = ""; $("q").value = ""; shown = 40; drawChips(); render();
      var y = $("listhead").getBoundingClientRect().top + window.pageYOffset - 84;
      window.scrollTo({ top: y, behavior: "smooth" });
    };
    $("sortsel").value = sortBy; $("kindsel").value = kindF;
  }
  $("sortsel").addEventListener("change", function () { sortBy = this.value; shown = 40; render(); });
  $("kindsel").addEventListener("change", function () { kindF = this.value; shown = 40; render(); });

  function header() {
    var d = new Date(DATA.updated);
    var when = isNaN(d) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    var tot = Math.max(1, DATA.cheaper_north + DATA.cheaper_south);
    var np = Math.round(100 * DATA.cheaper_north / tot);
    var lead = DATA.cheaper_south > DATA.cheaper_north ? 'The <span class="tS">South</span> has more cheaper items' :
      DATA.cheaper_north > DATA.cheaper_south ? 'The <span class="tN">North</span> has more cheaper items' : "Both sides have the same number of cheaper items";
    $("stats").innerHTML = '<div class="score"><button type="button" class="sc N" data-s="N"><b>' + DATA.cheaper_north + "</b><span>cheaper in the North</span><i>Tap to see them</i></button>" +
      '<button type="button" class="sc S" data-s="S"><b>' + DATA.cheaper_south + "</b><span>cheaper in the South</span><i>Tap to see them</i></button></div>" +
      '<div class="bar" role="img" aria-label="' + np + '% of products cheaper in the North"><span class="bN" style="width:' + np + '%"></span><span class="bS"></span></div>' +
      '<p class="score-f">' + DATA.count + " products compared" + (when ? ", updated " + when : "") + ".</p>";
    var src = Object.keys(DATA.sources || {}).map(function (k) {
      var s = DATA.sources[k], t = new Date(s.fetched_at);
      return esc(s.store) + " (" + s.products + " products, " + (isNaN(t) ? "" : t.toLocaleDateString("en-GB")) + ")";
    }).join(" · ");
    $("foot").innerHTML = "<p><b>Exchange rate:</b> 1 € = " + (DATA.fx ? DATA.fx.eur_try.toFixed(2) : "?") + " ₺ (" + esc(DATA.fx && DATA.fx.date) +
      ", European Central Bank)</p><p><b>Sources:</b> " + (src || "none yet") + ". <span class=\"tS\">South</span> prices come from the Cyprus government’s " +
      '<a href="https://www.e-kalathi.gov.cy" target="_blank" rel="noopener">e-kalathi</a> price observatory; <span class="tN">North</span> prices are the shops’ own online prices.</p><p><a href="privacy.html">Privacy policy</a></p>' +
      "<p>Prices are read automatically once a day and can change or differ in store. Products are paired like for like: same brand and same pack size; " +
      "“any brand” items compare the cheapest pack of the same size on both sides. Different pack sizes are never compared.</p>";
  }

  // three views, one at a time: Prices, Wanted, Add a price
  var curView = null;
  function showView() {
    var v = (location.hash || "").slice(1);
    if (v.indexOf("item=") === 0) {                      // a product page sits on top of the Prices list
      if (curView === null) setView("prices", true);
      sheetEl.onclick = null;
      if (DATA && !openSheet(decodeURIComponent(v.slice(5)))) location.hash = "#prices";
      drawMine();
      return;
    }
    if (v === "list") {                                   // My list sits on top of the Prices list too
      if (curView === null) setView("prices", true);
      if (DATA) openList();
      drawMine();
      return;
    }
    sheetEl.onclick = null;
    closeSheet();
    if (["prices", "wanted", "contrib"].indexOf(v) < 0) v = "prices";
    setView(v, v !== curView);
  }
  function setView(v, scroll) {
    curView = v;
    ["prices", "wanted", "contrib"].forEach(function (id) { $(id).hidden = id !== v; });
    Array.prototype.forEach.call(document.querySelectorAll(".tabbar a"), function (a) {
      var on = a.getAttribute("data-view") === v;
      a.classList.toggle("on", on);
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    if (scroll) window.scrollTo(0, 0);
    drawMine();
  }
  window.addEventListener("hashchange", showView);
  showView();

  var sideF = "";
  function toList() { window.scrollTo({ top: $("listhead").getBoundingClientRect().top + window.pageYOffset - 84, behavior: "smooth" }); }
  $("stats").addEventListener("click", function (e) {
    var b = e.target.closest(".sc"); if (!b) return;
    sideF = sideF === b.getAttribute("data-s") ? "" : b.getAttribute("data-s"); shown = 40; render(); if (sideF) toList();
  });
  $("sidef").addEventListener("click", function () { sideF = ""; shown = 40; render(); });
  $("qx").addEventListener("click", function () { query = ""; $("q").value = ""; shown = 40; drawChips(); render(); $("q").focus(); });
  $("out").addEventListener("click", function (e) {          // the whole product box opens its page
    if (e.target.closest("a, button")) return;
    var c = e.target.closest(".item[data-href]"); if (!c) return;
    cameFromList = true; location.hash = c.getAttribute("data-href");
  });
  var topB = $("totop");
  topB.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
  window.addEventListener("scroll", function () { topB.hidden = window.pageYOffset < 900 || curView !== "prices"; }, { passive: true });
  $("q").addEventListener("input", function () { query = this.value; shown = 40; drawChips(); render(); });
  $("more").addEventListener("click", function () { shown += 40; render(); });

  fetch("data/prices.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (d) {
    DATA = d; window.CC_DATA = d; DATA.items.forEach(index);
    header(); drawChips(); render(); drawMine();
    if (/^#(item=|list$)/.test(location.hash || "")) showView();
  }).catch(function () {
    $("out").innerHTML = '<div class="empty"><div class="name">Prices didn’t load</div><p class="small">Check your connection and pull down to refresh.</p></div>';
  });
})();
