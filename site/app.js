// Compare Cyprus – reads data/prices.json (written by the daily scraper) and shows it.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var DATA = null, query = "", cat = "", shown = 40, sortBy = "eur";

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
    var img = safeUrl(it.image) ? '<img loading="lazy" alt="" src="' + esc(it.image) + '" onerror="this.replaceWith(document.createTextNode(\'' + icon(it) + '\'))">' : icon(it);
    var verdict = it.cheaper === "=" ? '<div class="verdict same">Same price on both sides</div>' : "";
    var chains = ["Lidl", "AlphaMega"].map(function (c) {
      var o = it.south.filter(function (x) { return x.store === c; })[0];
      return o && o !== s ? "<b>" + c + "</b> " + eur(o.shelf ? o.shelf.eur : o.eur) : "";
    }).filter(Boolean).join(", ");
    var extra = it.north.length + it.south.length - 2;
    var on = others(it.north), os = others(it.south);
    var more = extra > 0 ? '<div class="olist' + (on && os ? "" : " one") + '">' + (on ? '<div class="N"><h4 class="tN">Other North shops</h4>' + on + "</div>" : "") +
      (os ? '<div class="S"><h4 class="tS">Other South shops</h4>' + os + "</div>" : "") + "</div>" : "";
    var note = it.kind !== "exact" && it.note ? '<p class="note">' + esc(it.note) + "</p>" : "";
    return '<article class="item"><div class="head"><div class="art">' + img + '</div><div class="ttl"><h3 class="name">' + esc(nice(it.name)) +
      '</h3><div class="unit">' + esc([it.unit, it.category].filter(Boolean).join(" · ")) + '</div></div></div><div class="tags">' +
      side("North", "N", n, it.cheaper === "N", it) + side("South", "S", s, it.cheaper === "S", it) + "</div>" + verdict +
      (chains ? '<div class="chains">Also in the <span class="tS">South</span>: ' + chains + "</div>" : "") +
      '<details class="more"><summary>Shops and details' + (extra > 0 ? " (" + extra + " more " + (extra === 1 ? "price" : "prices") + ")" : "") +
      '</summary><div class="whs">' + where("North", "N", n, per) + where("South", "S", s, per) + "</div>" + more + note + "</details></article>";
  }

  function render() {
    var q = fold(query).trim();
    var list = DATA.items.map(function (it) { return { it: it, s: (!cat || it.group === cat) ? score(it, q) : 0 }; })
      .filter(function (x) { return x.s > 0; })
      .sort(function (a, b) {
        var bySaving = sortBy === "pct" ? b.it.saving_pct - a.it.saving_pct : gap(b.it) - gap(a.it);
        return b.s - a.s || (q ? a.it.name.length - b.it.name.length : 0) || bySaving;
      })
      .map(function (x) { return x.it; });
    $("listhead").textContent = q ? list.length + (list.length === 1 ? " result" : " results") + " for “" + query + "”" :
      (cat || "All products") + " (" + list.length + ")";
    var html = list.slice(0, shown).map(card).join("");
    if (!DATA.items.length) {
      html = '<div class="empty"><div class="name">Prices appear after the first daily run</div><p class="small">The scraper runs every morning and fills this page automatically.</p></div>';
    } else if (!list.length) {
      html = '<div class="empty"><div class="name">No comparison for “' + esc(query) + '” yet</div><p class="small">An item shows up once the same product (brand and size) is on sale in both <span class="tN">North</span> and <span class="tS">South</span>. Try a shorter word, such as a brand name.</p></div>';
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
    $("sort").innerHTML = [["eur", "€ saved"], ["pct", "% saved"]].map(function (o) {
      return '<button type="button" class="' + (sortBy === o[0] ? "on" : "") + '" data-v="' + o[0] + '" aria-pressed="' + (sortBy === o[0]) + '">' + o[1] + "</button>";
    }).join("");
    $("sort").onclick = function (e) {
      var b = e.target.closest("button"); if (!b) return;
      sortBy = b.getAttribute("data-v"); shown = 40; drawChips(); render();
    };
  }

  function header() {
    var d = new Date(DATA.updated);
    var when = isNaN(d) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    var tot = Math.max(1, DATA.cheaper_north + DATA.cheaper_south);
    var np = Math.round(100 * DATA.cheaper_north / tot);
    var lead = DATA.cheaper_south > DATA.cheaper_north ? 'The <span class="tS">South</span> has more cheaper items' :
      DATA.cheaper_north > DATA.cheaper_south ? 'The <span class="tN">North</span> has more cheaper items' : "Both sides have the same number of cheaper items";
    $("stats").innerHTML = '<div class="score"><div class="sc N"><b>' + DATA.cheaper_north + "</b><span>cheaper in the North</span></div>" +
      '<div class="sc S"><b>' + DATA.cheaper_south + "</b><span>cheaper in the South</span></div></div>" +
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
  function showView() {
    var v = (location.hash || "").slice(1);
    if (["prices", "wanted", "contrib"].indexOf(v) < 0) v = "prices";
    ["prices", "wanted", "contrib"].forEach(function (id) { $(id).hidden = id !== v; });
    Array.prototype.forEach.call(document.querySelectorAll(".tabbar a"), function (a) {
      var on = a.getAttribute("data-view") === v;
      a.classList.toggle("on", on);
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", showView);
  showView();

  $("q").addEventListener("input", function () { query = this.value; shown = 40; drawChips(); render(); });
  $("more").addEventListener("click", function () { shown += 40; render(); });

  fetch("data/prices.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (d) {
    DATA = d; window.CC_DATA = d; DATA.items.forEach(index);
    header(); drawChips(); render();
  }).catch(function () {
    $("out").innerHTML = '<div class="empty"><div class="name">Prices didn’t load</div><p class="small">Check your connection and pull down to refresh.</p></div>';
  });
})();
