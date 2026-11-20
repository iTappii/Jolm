// Place picker for the event form (no inline scripts: CSP allows only same-origin files).
document.addEventListener("click", function (ev) {
  var btn = ev.target.closest("[data-pick-place]");
  if (!btn) return;
  var id = document.getElementById("place_id");
  var label = document.getElementById("place_label");
  if (id) id.value = btn.getAttribute("data-place-id");
  if (label) label.textContent = btn.getAttribute("data-place-name");
  var list = btn.closest(".pick-list");
  if (list) list.remove();
});
document.addEventListener("click", function (ev) {
  if (ev.target.closest("[data-clear-place]")) {
    var id = document.getElementById("place_id");
    var label = document.getElementById("place_label");
    if (id) id.value = "";
    if (label) label.textContent = "не выбрано";
  }
});
document.addEventListener("submit", function (ev) {
  var msg = ev.target.getAttribute("data-confirm");
  if (msg && !window.confirm(msg)) ev.preventDefault();
});
