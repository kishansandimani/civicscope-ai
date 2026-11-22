// Small accessible UI helpers: toasts (aria-live) and busy buttons, styled in the Midnight Hypergraph palette.
let region;
function ensureRegion() {
  if (region) return region;
  region = document.createElement("div");
  region.setAttribute("role", "status");
  region.setAttribute("aria-live", "polite");
  region.className = "fixed bottom-6 right-6 z-[100] flex flex-col gap-2 max-w-sm";
  document.body.appendChild(region);
  return region;
}
export function toast(message, kind = "info") {
  const colors = { info: "border-cyan-400/40", success: "border-emerald-400/50", error: "border-rose-400/60", warning: "border-amber-400/50" };
  const el = document.createElement("div");
  el.className = `px-4 py-3 rounded-xl bg-[#101221]/95 backdrop-blur-2xl border ${colors[kind] || colors.info} text-sm text-white shadow-[0_10px_30px_rgba(0,0,0,0.6)]`;
  el.textContent = message;
  ensureRegion().appendChild(el);
  setTimeout(() => el.remove(), kind === "error" ? 8000 : 4500);
}
export async function withBusy(btn, fn) {
  if (!btn) return fn();
  const label = btn.innerHTML;
  btn.disabled = true; btn.setAttribute("aria-busy", "true"); btn.classList.add("opacity-60", "cursor-wait");
  try { return await fn(); }
  finally { btn.disabled = false; btn.removeAttribute("aria-busy"); btn.classList.remove("opacity-60", "cursor-wait"); btn.innerHTML = label; }
}
export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
