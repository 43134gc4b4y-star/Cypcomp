// "Get the app": install button on Android/desktop Chrome, instructions on iPhone.
(function () {
  "use strict";
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(function () {});
  var box = document.getElementById("install"), btn = document.getElementById("installBtn"), how = document.getElementById("installHow");
  var standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  var hidden = false;
  try { hidden = localStorage.getItem("cc-install-hidden") === "1"; } catch (e) { /* private mode */ }
  if (standalone || hidden) return;
  var deferred = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault(); deferred = e; box.hidden = false;
  });
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  if (ios) {
    box.hidden = false;
    how.innerHTML = "Tap <b>Share</b> then <b>Add to Home Screen</b>.";
    btn.hidden = true;
  }
  btn.addEventListener("click", function () {
    if (!deferred) return;
    deferred.prompt();
    deferred.userChoice.then(function () { deferred = null; box.hidden = true; });
  });
  document.getElementById("installX").addEventListener("click", function () {
    box.hidden = true;
    try { localStorage.setItem("cc-install-hidden", "1"); } catch (e) { /* ignore */ }
  });
  window.addEventListener("appinstalled", function () { box.hidden = true; });
})();
