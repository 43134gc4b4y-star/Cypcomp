// "Add a price" – shoppers send a price they saw. Answers go to the owner's Google Form,
// are checked by hand, and the daily job puts approved ones on the site.
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var CFG = null, stream = null, timer = null, detector = null;
  var form = $("cform");

  fetch("contribute.json", { cache: "no-cache" }).then(function (r) { return r.json(); })
    .then(function (c) { CFG = c; }).catch(function () { CFG = null; });

  function ean(code) {
    if (!/^\d+$/.test(code) || [8, 12, 13, 14].indexOf(code.length) < 0) return false;
    var d = code.split("").map(Number), last = d.pop(), sum = 0;
    d.reverse().forEach(function (x, i) { sum += x * (i % 2 ? 1 : 3); });
    return (10 - sum % 10) % 10 === last;
  }

  function lookup(code) {
    var data = window.CC_DATA, hits = [];
    if (!data) return hits;
    data.items.forEach(function (it) {
      ["north", "south"].forEach(function (s) {
        (it[s] || []).forEach(function (o) { if (o.barcode === code && hits.indexOf(it) < 0) hits.push(it); });
      });
    });
    return hits;
  }

  function gotCode(code) {
    code = String(code).replace(/\D/g, "");
    stop();
    form.barcode.value = code;
    var msg = ean(code) ? "✅ Barcode " + code : "⚠️ Read " + code + " – please check it against the numbers on the pack";
    var hits = lookup(code);
    if (hits.length) {
      msg += '<div class="found">Already on the site: <b>' + hits[0].name.replace(/</g, "&lt;") +
        "</b>. Your price will be added to it.</div>";
      if (!form.product.value) form.product.value = hits[0].name;
    } else {
      msg += '<div class="found">Not on the site yet – send it anyway; it appears once there is a price from the other side too.</div>';
    }
    $("scanmsg").innerHTML = msg;
    if (navigator.vibrate) navigator.vibrate(80);
    if (!$("cfor").hidden) form.price.focus();
  }

  // Reader: the phone's own barcode reader if it has one (Android Chrome), otherwise ZXing.
  var zxing = null;
  function loadZxing() {
    if (zxing) return zxing;
    zxing = new Promise(function (ok, bad) {
      var s = document.createElement("script");
      s.src = "https://unpkg.com/@zxing/library@0.21.3/umd/index.min.js";
      s.onload = function () { ok(window.ZXing); }; s.onerror = bad;
      document.head.appendChild(s);
    });
    return zxing;
  }
  function native() {
    if (detector !== null) return detector;
    detector = false;
    if ("BarcodeDetector" in window) {
      try { detector = new window.BarcodeDetector({ formats: ["ean_13", "ean_8", "upc_a", "upc_e"] }); } catch (e) { detector = false; }
    }
    return detector;
  }

  function stop() {
    clearInterval(timer); timer = null;
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null; $("scanbox").hidden = true;
    if (window._zx) { try { window._zx.reset(); } catch (e) { /* ignore */ } window._zx = null; }
  }

  $("scanbtn").addEventListener("click", function () {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      $("scanmsg").textContent = "This browser can't use the camera – try “Use a photo”, or type the numbers.";
      return;
    }
    $("scanmsg").textContent = "Point the camera at the barcode…";
    var vid = $("scanvid");
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } }).then(function (s) {
      stream = s; vid.srcObject = s; $("scanbox").hidden = false; return vid.play();
    }).then(function () {
      var d = native();
      if (d) {
        timer = setInterval(function () {
          d.detect(vid).then(function (r) { if (r.length) gotCode(r[0].rawValue); }).catch(function () {});
        }, 250);
      } else {
        return loadZxing().then(function (Z) {
          var r = new Z.BrowserMultiFormatReader(); window._zx = r;
          r.decodeFromStream(stream, vid, function (res) { if (res) gotCode(res.getText()); });
        });
      }
    }).catch(function () {
      stop();
      $("scanmsg").textContent = "Couldn't open the camera (permission?). Try “Use a photo”, or type the numbers.";
    });
  });
  $("scanstop").addEventListener("click", function () { stop(); $("scanmsg").textContent = ""; });

  $("scanphoto").addEventListener("change", function () {
    var f = this.files && this.files[0];
    if (!f) return;
    $("scanmsg").textContent = "Reading the photo…";
    var img = new Image();
    img.onload = function () {
      var fail = function () { $("scanmsg").textContent = "No barcode found in that photo – try closer and sharper, or type the numbers."; };
      var d = native();
      var viaZxing = function () {
        loadZxing().then(function (Z) { return new Z.BrowserMultiFormatReader().decodeFromImageElement(img); })
          .then(function (res) { gotCode(res.getText()); }).catch(fail);
      };
      if (d) d.detect(img).then(function (r) { if (r.length) gotCode(r[0].rawValue); else viaZxing(); }).catch(viaZxing);
      else viaZxing();
    };
    img.src = URL.createObjectURL(f);
  });

  form.barcode.addEventListener("change", function () { if (this.value.replace(/\D/g, "").length >= 8) gotCode(this.value); });

  form.side.forEach(function (r) {
    r.addEventListener("change", function () { form.currency.value = r.value === "North" ? "TRY" : "EUR"; });
  });

  // From the Wanted list: fill in what we already know, then open the camera for the barcode
  window.CC_prefill = function (w, openCamera) {
    var side = w.need === "S" ? "South" : "North";
    form.side.forEach(function (r) { r.checked = r.value === side; });
    form.currency.value = side === "North" ? "TRY" : "EUR";
    form.product.value = w.name; form.size.value = w.size || ""; form.barcode.value = w.barcode || "";
    form.price.value = ""; $("cmsg").textContent = ""; $("scanmsg").textContent = "";
    $("cfor").hidden = false;
    $("cfor").innerHTML = "Adding the <b>" + side + "</b> price for <b>" + w.name.replace(/</g, "&lt;") + "</b>. " +
      "Photograph the barcode, then type the price and shop.";
    document.getElementById("contrib").scrollIntoView({ behavior: "smooth", block: "start" });
    if (openCamera) $("scanphoto").click();
    else setTimeout(function () { form.price.focus(); }, 400);
  };

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var v = {
      side: form.side.value, shop: form.shop.value.trim(), town: form.town.value.trim(),
      product: form.product.value.trim(), barcode: form.barcode.value.replace(/\D/g, ""),
      size: form.size.value.trim(), price: form.price.value.trim(), currency: form.currency.value, note: form.note.value.trim()
    };
    var p = parseFloat(v.price.replace(",", "."));
    if (!(p > 0)) { $("cmsg").textContent = "Please enter the price as a number, e.g. 45.50"; return; }
    if (!CFG || !CFG.form_action) {
      $("cmsg").textContent = "Thanks! Sending isn't switched on yet – please try again in a few days.";
      return;
    }
    var body = new URLSearchParams();
    Object.keys(CFG.fields).forEach(function (k) { if (CFG.fields[k]) body.append(CFG.fields[k], v[k] || ""); });
    $("cmsg").textContent = "Sending…";
    fetch(CFG.form_action, { method: "POST", mode: "no-cors", body: body }).then(function () {
      $("cmsg").textContent = "✅ Thank you! It will be checked and should appear within a day or two.";
      ["product", "size", "price", "barcode", "note"].forEach(function (k) { form[k].value = ""; });
      $("cfor").hidden = true;
      $("scanmsg").textContent = "";
    }).catch(function () { $("cmsg").textContent = "Couldn't send – check your connection and try again."; });
  });
})();
