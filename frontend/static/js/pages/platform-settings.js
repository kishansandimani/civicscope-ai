import { api } from "../api.js";
import { supabase } from "../supabase-client.js";
import { toast, withBusy } from "../ui.js";
import { el, chip, emptyState, errorState } from "../render.js";

const $ = (s) => document.querySelector(s);

async function loadProfile() {
  try {
    const me = await api("/me");
    $("#ps-email").value = me.email || ""; $("#ps-name").value = me.full_name || ""; $("#ps-role").value = me.designation || "";
    $("#ps-org").value = me.organization || ""; $("#ps-lang").value = me.preferred_language || "en";
    const s = await api("/settings"); $("#ps-notify").checked = s.notify_in_app !== false;
  } catch (e) { toast(e.message, "error"); }
}

async function loadNotes() {
  const ul = $("#ps-notes");
  try {
    const { items } = await api("/notifications"); ul.replaceChildren();
    if (!items.length) { ul.appendChild(el("li", "text-sm text-violet-300/70", "No notifications yet.")); return; }
    items.forEach(n => {
      const li = el("li", `rounded-xl border border-white/10 p-3 ${n.is_read ? "opacity-70" : "bg-white/5"}`);
      const h = el("div", "flex items-center gap-2"); h.append(chip(n.kind, n.kind === "error" ? "high" : n.kind === "warning" ? "medium" : n.kind === "success" ? "met" : "low"), el("span", "font-semibold text-white text-sm", n.title));
      li.append(h, el("p", "text-xs text-violet-100/80 mt-1", n.message || ""), el("p", "text-[11px] text-violet-300/60 mt-1", new Date(n.created_at).toLocaleString()));
      ul.appendChild(li);
    });
  } catch (e) { ul.replaceChildren(errorState(e.message)); }
}

$("#ps-profile").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("#ps-name").value.trim();
  if (!name) { toast("Your name cannot be empty.", "warning"); $("#ps-name").focus(); return; }
  await withBusy(e.submitter, async () => {
    try { await api("/me", { method: "PATCH", body: { full_name: name, designation: $("#ps-role").value.trim(), organization: $("#ps-org").value.trim(), preferred_language: $("#ps-lang").value } }); toast("Profile saved.", "success"); }
    catch (err) { toast(err.message, "error"); }
  });
});

$("#ps-password").addEventListener("submit", async (e) => {
  e.preventDefault();
  const a = $("#ps-pw1").value, b = $("#ps-pw2").value;
  if (a.length < 8) return toast("Password must be at least 8 characters.", "warning");
  if (a !== b) return toast("The two passwords do not match.", "warning");
  await withBusy(e.submitter, async () => {
    const { error } = await supabase.auth.updateUser({ password: a });
    if (error) toast(error.message, "error"); else { toast("Password updated.", "success"); $("#ps-pw1").value = $("#ps-pw2").value = ""; }
  });
});

$("#ps-signout").addEventListener("click", async () => { await supabase.auth.signOut(); location.href = "/login"; });
$("#ps-notify").addEventListener("change", async (e) => { try { await api("/settings", { method: "PATCH", body: { notify_in_app: e.target.checked } }); toast("Notification setting saved.", "success"); } catch (err) { toast(err.message, "error"); e.target.checked = !e.target.checked; } });
$("#ps-readall").addEventListener("click", async () => { try { await api("/notifications/read-all", { method: "POST" }); await loadNotes(); } catch (e) { toast(e.message, "error"); } });

loadProfile(); loadNotes();
