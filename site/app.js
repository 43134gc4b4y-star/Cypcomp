// Compare Cyprus – reads data/prices.json (written by the daily scraper) and shows it.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var DATA = null, query = "", cat = "", shown = 40;

  var TRENDING = ["milk", "coffee", "cola", "eggs", "halloumi", "honey", "nappies", "baby milk", "tissue", "protein bar", "olive oil", "tomatoes"];
  // English search words -> Turkish/Greek words shops use, so "milk" also finds "süt"
  var ALIAS = {
    milk: ["sut", "gala"], coffee: ["kahve", "nescafe"], tea: ["cay"], honey: ["bal"], eggs: ["yumurta", "avga"], egg: ["yumurta"],
    cheese: ["peynir"], halloumi: ["hellim"], water: ["su "], bread: ["ekmek"], butter: ["tereyag"], yoghurt: ["yogurt"],
    nappies: ["bebek bezi", "pampers", "diaper", "molfix", "huggies"], diapers: ["nappies", "bebek bezi"],
    "baby milk": ["aptamil", "bebelac", "nan ", "hipp", "formula", "devam sutu", "bebek sutu"],
    tissue: ["mendil", "tissues", "selpak", "kleenex"], "toilet paper": ["tuvalet kagidi"], cola: ["coca", "pepsi", "kola"],
    "protein bar": ["protein"], chocolate: ["cikolata"], rice: ["pirinc"], pasta: ["makarna"], sugar: ["seker"],
    flour: ["un "], "olive oil": ["zeytinyag", "olive oil"], oil: ["yag"], tomatoes: ["domates", "tomato"], potatoes: ["patates"],
    shampoo: ["sampuan"], detergent: ["deterjan"], toothpaste: ["dis macunu"], soap: ["sabun"], beer: ["bira"], wine: ["sarap"]
  };
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

  function index(it) {
    var parts = [it.name, it.category, it.unit];
    it.north.concat(it.south).forEach(function (o) { parts.push(o.name, o.store); });
    it._t = " " + fold(parts.join(" ")) + " ";
  }

  function matches(it, q) {
    if (!q) return true;
    var alts = [q].concat(ALIAS[q] || []);
    return alts.some(function (a) {
      return fold(a).trim().split(/\s+/).every(function (w) { return it._t.indexOf(" " + w) >= 0 || it._t.indexOf(w) >= 0 && w.length > 3; });
    });
  }

  function side(label, cls, o, win, mainCur) {
    var big = mainCur === "TRY" ? tl(o.try) : eur(o.eur), small = mainCur === "TRY" ? eur(o.eur) : tl(o.try);
    var btn = "";
    if (safeUrl(o.maps)) btn += '<a class="go" target="_blank" rel="noopener" href="' + esc(o.maps) + '">📍 Map</a>';
    if (safeUrl(o.url)) btn += '<a class="go" target="_blank" rel="noopener" href="' + esc(o.url) + '">🛒 Shop page</a>';
    var shelf = o.shelf ? '<div class="tw">' + esc(o.shelf.name) + "</div>" : '<div class="tw">' + esc(o.name) + "</div>";
    return '<div class="side ' + cls + (win ? " win" : "") + '"><div class="lab"><span>' + label + "</span>" + (win ? '<span class="tag">CHEAPER</span>' : "") +
      '</div><div class="pr">' + big + '</div><div class="pl">' + small + '</div><div class="sn">' + esc(o.store) + "</div>" +
      (o.town ? '<div class="tw">' + esc(o.town) + "</div>" : "") + shelf + '<div class="btns">' + btn + "</div></div>";
  }

  function others(list, cur) {
    return list.slice(1).map(function (o) {
      var p = eur(o.eur) + ' <span class="pl">' + tl(o.try) + "</span>";
      var nm = safeUrl(o.url) ? '<a target="_blank" rel="noopener" href="' + esc(o.url) + '">' + esc(o.store) + "</a>" : esc(o.store);
      return "<div><span>" + nm + "</span><b>" + p + "</b></div>";
    }).join("");
  }

  function card(it) {
    var n = it.north[0], s = it.south[0];
    var badge = it.cheaper === "=" ? '<span class="sv E">Same price</span>'
      : '<span class="sv ' + it.cheaper + '">' + (it.cheaper === "N" ? "North" : "South") + " saves " + Math.round(it.saving_pct) + "%</span>";
    var img = safeUrl(it.image) ? '<img loading="lazy" alt="" src="' + esc(it.image) + '" onerror="this.replaceWith(document.createTextNode(\'' + icon(it) + '\'))">' : icon(it);
    var more = "";
    if (it.north.length > 1 || it.south.length > 1) {
      more = '<details class="others"><summary>Other stores</summary><div class="olist"><div style="display:block">' + others(it.north, "EUR") +
        '</div><div style="display:block">' + others(it.south, "EUR") + "</div></div></details>";
    }
    var note = it.kind !== "exact" && it.note ? '<div class="note">' + esc(it.note) + (n.date ? " · " + esc(n.date) : "") + "</div>" : "";
    return '<article class="card"><div class="head"><div class="art">' + img + '</div><div class="ttl"><div class="name">' + esc(it.name) +
      '</div><div class="unit">' + esc([it.unit, it.category].filter(Boolean).join(" · ")) + "</div></div>" + badge + '</div><div class="sides">' +
      side("NORTH", "N", n, it.cheaper === "N", "EUR") + side("SOUTH", "S", s, it.cheaper === "S", "EUR") + "</div>" + more + note + "</article>";
  }

  function render() {
    var list = DATA.items.filter(function (it) { return (!cat || it.category === cat) && matches(it, fold(query).trim()); });
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
    DATA = d; DATA.items.forEach(index); header(); drawChips(); render();
  }).catch(function () {
    $("out").innerHTML = '<div class="card empty"><div class="big">⚠️</div><div class="name">Could not load prices</div><p class="small">Please try again in a moment.</p></div>';
  });
})();
