// Compare Cyprus – reads data/prices.json (written by the daily scraper) and shows it.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var DATA = null, query = "", cat = "", shown = 40;

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
  var CAT_ICON = [[/fuel|petrol|diesel/i, "⛽"], [/milk|dairy|cheese|yogh|egg/i, "🥛"], [/coffee|tea/i, "☕"], [/drink|soft|water|juice|beverage/i, "🥤"],
    [/fruit|veg/i, "🥬"], [/meat|chicken|fish/i, "🍗"], [/baby|nappy|diaper/i, "🍼"], [/bread|bak/i, "🍞"], [/snack|choc|sweet|biscuit/i, "🍫"],
    [/clean|detergent|household/i, "🧴"], [/personal|care|hygiene|shampoo/i, "🧼"], [/paper|tissue/i, "🧻"], [/pet/i, "🐾"]];

  function fold(s) {
    return (s || "").toLowerCase().replace(/ı/g, "i").replace(/ş/g, "s").replace(/ğ/g, "g").replace(/ç/g, "c").replace(/ö/g, "o").replace(/ü/g, "u")
      .normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function eur(v) { return "€" + v.toFixed(2); }
  function tl(v) { return v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " ₺"; }
  function safeUrl(u) { return /^https?:\/\//i.test(u || "") ? u : ""; }
  function icon(it) { for (var i = 0; i < CAT_ICON.length; i++) if (CAT_ICON[i][0].test(it.category + " " + it.name)) return CAT_ICON[i][1]; return "🛒"; }

  function words(t) { return fold(t).split(/[^a-z0-9]+/).filter(Boolean); }

  function index(it) {
    it._n = words(it.name);
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

  function perLabel(it) {
    var m = /price (per [^·]+)/.exec(it.unit || "");
    return m ? m[1].trim().replace(/^per 1 l$/, "per litre").replace(/^per 1 kg$/, "per kg").replace(/^per 1 /, "per ") : "";
  }

  function side(label, cls, o, win, mainCur, per) {
    // shelf price large; for per-kg/litre comparisons the unit price goes underneath
    var shelfEur = o.shelf ? o.shelf.eur : o.eur, shelfTry = o.shelf ? o.shelf.try : o.try;
    var big = eur(shelfEur), small = tl(shelfTry);
    var unit = o.shelf && per ? '<div class="unitp">' + eur(o.eur) + " " + esc(per) + " · " + tl(o.try) + "</div>" : "";
    var btn = "";
    if (safeUrl(o.maps)) btn += '<a class="go" target="_blank" rel="noopener" href="' + esc(o.maps) + '">📍 Map</a>';
    if (safeUrl(o.url)) btn += '<a class="go" target="_blank" rel="noopener" href="' + esc(o.url) + '">🛒 Shop page</a>';
    var shelf = o.shelf ? '<div class="tw">' + esc(o.shelf.name) + "</div>" : '<div class="tw">' + esc(o.name) + "</div>";
    return '<div class="side ' + cls + (win ? " win" : "") + '"><div class="lab"><span>' + label + "</span>" + (win ? '<span class="tag">CHEAPER</span>' : "") +
      '</div><div class="pr">' + big + '</div><div class="pl">' + small + "</div>" + unit + '<div class="sn">' + esc(o.store) + "</div>" +
      (o.town ? '<div class="tw">' + esc(o.town) + "</div>" : "") + shelf + '<div class="btns">' + btn + "</div></div>";
  }

  function others(list, cur) {
    return list.slice(1).map(function (o) {
      var p = o.shelf ? eur(o.shelf.eur) + ' <span class="pl">' + tl(o.shelf.try) + "</span>"
                      : eur(o.eur) + ' <span class="pl">' + tl(o.try) + "</span>";
      var nm = safeUrl(o.url) ? '<a target="_blank" rel="noopener" href="' + esc(o.url) + '">' + esc(o.store) + "</a>" : esc(o.store);
      return "<div><span>" + nm + "</span><b>" + p + "</b></div>";
    }).join("");
  }

  function card(it) {
    var n = it.north[0], s = it.south[0];
    var badge = it.cheaper === "=" ? '<span class="sv E">Same price</span>'
      : '<span class="sv ' + it.cheaper + '">' + (it.cheaper === "N" ? "North" : "South") + " saves " + Math.round(it.saving_pct) + "%" + (perLabel(it) && /pack sizes differ/.test(it.unit) ? " " + esc(perLabel(it)) : "") + "</span>";
    var img = safeUrl(it.image) ? '<img loading="lazy" alt="" src="' + esc(it.image) + '" onerror="this.replaceWith(document.createTextNode(\'' + icon(it) + '\'))">' : icon(it);
    var more = "";
    if (it.north.length > 1 || it.south.length > 1) {
      more = '<details class="others"><summary>Other stores</summary><div class="olist"><div style="display:block">' + others(it.north, "EUR") +
        '</div><div style="display:block">' + others(it.south, "EUR") + "</div></div></details>";
    }
    var chains = ["Lidl", "AlphaMega"].map(function (c) {
      var o = it.south.filter(function (x) { return x.store === c; })[0];
      if (!o) return "";
      var e = o.shelf ? o.shelf.eur : o.eur, t = o.shelf ? o.shelf.try : o.try;
      return "<span><b>" + c + "</b> " + eur(e) + ' <span class="pl">' + tl(t) + "</span></span>";
    }).filter(Boolean).join("");
    var chainRow = chains ? '<div class="chains">South chains: ' + chains + "</div>" : "";
    var note = it.kind !== "exact" && it.note ? '<div class="note">' + esc(it.note) + (n.date ? " · " + esc(n.date) : "") + "</div>" : "";
    return '<article class="card"><div class="head"><div class="art">' + img + '</div><div class="ttl"><div class="name">' + esc(it.name) +
      '</div><div class="unit">' + esc([it.unit, it.category].filter(Boolean).join(" · ")) + "</div></div>" + badge + '</div><div class="sides">' +
      side("NORTH", "N", n, it.cheaper === "N", "EUR", perLabel(it)) + side("SOUTH", "S", s, it.cheaper === "S", "EUR", perLabel(it)) + "</div>" + chainRow + more + note + "</article>";
  }

  function render() {
    var q = fold(query).trim();
    var list = DATA.items.map(function (it) { return { it: it, s: (!cat || it.category === cat) ? score(it, q) : 0 }; })
      .filter(function (x) { return x.s > 0; })
      .sort(function (a, b) { return b.s - a.s || (q ? a.it.name.length - b.it.name.length : 0) || b.it.saving_pct - a.it.saving_pct; })
      .map(function (x) { return x.it; });
    var html = list.slice(0, shown).map(card).join("");
    if (!DATA.items.length) {
      html = '<div class="card empty"><div class="big">⏳</div><div class="name">Prices appear after the first daily run</div><p class="small">The scraper runs every morning and fills this page automatically.</p></div>';
    } else if (!list.length) {
      html = '<div class="card empty"><div class="big">🔎</div><div class="name">No comparison for “' + esc(query) + '” yet</div><p class="small">An item shows up once the same product (brand and size) is on sale in both North and South. Try a shorter word, such as a brand name.</p></div>';
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
    chips($("trending"), TRENDING.map(function (t) { return { t: t, v: t }; }), query, function (v) {
      query = query === v ? "" : v; $("q").value = query; shown = 40; drawChips(); render();
    });
    var counts = {};
    DATA.items.forEach(function (i) { counts[i.category] = (counts[i.category] || 0) + 1; });
    var cats = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; }).slice(0, 20);
    chips($("cats"), [{ t: "All", v: "" }].concat(cats.map(function (c) { return { t: c + " (" + counts[c] + ")", v: c }; })), cat, function (v) {
      cat = v; shown = 40; drawChips(); render();
    });
  }

  function header() {
    var d = new Date(DATA.updated);
    var when = isNaN(d) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    $("stats").innerHTML = "<span>" + DATA.count + " items compared</span><span>North cheaper: " + DATA.cheaper_north +
      "</span><span>South cheaper: " + DATA.cheaper_south + "</span>" + (when ? "<span>Updated " + when + "</span>" : "");
    var src = Object.keys(DATA.sources || {}).map(function (k) {
      var s = DATA.sources[k], t = new Date(s.fetched_at);
      return esc(s.store) + " (" + s.products + " products, " + (isNaN(t) ? "" : t.toLocaleDateString("en-GB")) + ")";
    }).join(" · ");
    $("foot").innerHTML = "<p><b>Exchange rate:</b> 1 € = " + (DATA.fx ? DATA.fx.eur_try.toFixed(2) : "?") + " ₺ (" + esc(DATA.fx && DATA.fx.date) +
      ", European Central Bank)</p><p><b>Sources:</b> " + (src || "none yet") + ". South prices come from the Cyprus government’s " +
      '<a href="https://www.e-kalathi.gov.cy" target="_blank" rel="noopener">e-kalathi</a> price observatory; North prices are the shops’ own online prices.</p>' +
      "<p>Prices are read automatically once a day and can change or differ in store. Products are paired by brand and pack size; " +
      "“any brand” items such as vegetables compare the cheapest option per kg.</p>";
  }

  $("q").addEventListener("input", function () { query = this.value; shown = 40; drawChips(); render(); });
  $("more").addEventListener("click", function () { shown += 40; render(); });

  fetch("data/prices.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (d) {
    DATA = d; DATA.items.forEach(index);
    TRENDING = TRENDING_CANDIDATES.filter(function (t) { return DATA.items.some(function (it) { return score(it, t) >= 2.5; }); }).slice(0, 12);
    header(); drawChips(); render();
  }).catch(function () {
    $("out").innerHTML = '<div class="card empty"><div class="big">⚠️</div><div class="name">Could not load prices</div><p class="small">Please try again in a moment.</p></div>';
  });
})();
