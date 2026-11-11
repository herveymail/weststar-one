// Weststar ONE tech app: register the service worker, live timers, auto-submit status, photo count, fade messages.
(function () {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () { navigator.serviceWorker.register("/tech/sw.js", { scope: "/tech/" }).catch(function () {}); });
  }
  function pad(n) { return n < 10 ? "0" + n : "" + n; }
  function tick() {
    document.querySelectorAll("[data-since]").forEach(function (el) {
      var s = Math.max(0, Math.floor((Date.now() - Date.parse(el.getAttribute("data-since"))) / 1000));
      el.textContent = Math.floor(s / 3600) + ":" + pad(Math.floor(s / 60) % 60) + ":" + pad(s % 60);
    });
  }
  document.addEventListener("DOMContentLoaded", function () {
    tick(); setInterval(tick, 1000);
    document.querySelectorAll("[data-autosubmit]").forEach(function (el) { el.addEventListener("change", function () { el.form.submit(); }); });
    document.querySelectorAll("[data-count]").forEach(function (el) {
      el.addEventListener("change", function () {
        var lab = el.form.querySelector("[data-count-label]");
        if (lab) lab.textContent = el.files.length ? el.files.length + " photo" + (el.files.length > 1 ? "s" : "") + " ready to save" : "";
      });
    });
    // Don't send a form twice on a slow connection.
    document.querySelectorAll("form").forEach(function (f) {
      f.addEventListener("submit", function () { setTimeout(function () { f.querySelectorAll("button").forEach(function (b) { b.disabled = true; }); }, 0); });
    });
    setTimeout(function () { document.querySelectorAll(".toast").forEach(function (t) { t.classList.add("hide"); }); }, 3500);
    setTimeout(function () { var t = document.querySelector(".toasts"); if (t) t.remove(); }, 4200);
    var standalone = window.navigator.standalone || window.matchMedia("(display-mode: standalone)").matches;
    if (standalone) document.querySelectorAll("[data-install]").forEach(function (el) { el.hidden = true; });
  });
  // Coming back to the app after a while: refresh so the numbers are current.
  var hiddenAt = 0;
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { hiddenAt = Date.now(); }
    else if (hiddenAt && Date.now() - hiddenAt > 5 * 60 * 1000 && !document.querySelector("textarea:not(:placeholder-shown)")) { location.reload(); }
  });
})();
