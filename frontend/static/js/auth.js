import { supabase, configured } from "./supabase-client.js";
import { toast, withBusy } from "./ui.js";

const mode = document.body.dataset.page; // login | register | forgot-password | reset-password
const form = document.getElementById("auth-form");
const errorBox = document.getElementById("auth-error");
const next = new URLSearchParams(location.search).get("next");
const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : "/overview";

function showError(msg) { errorBox.textContent = msg; errorBox.classList.remove("hidden"); errorBox.focus(); }
function clearError() { errorBox.classList.add("hidden"); errorBox.textContent = ""; }
const validEmail = v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

if (!configured) showError("Supabase is not configured on the server. Fill in backend/.env and restart.");

(async () => {
  if (!configured) return;
  const { data } = await supabase.auth.getSession();
  if (data.session && (mode === "login" || mode === "register")) location.href = safeNext;
})();

if (mode === "reset-password") {
  // Supabase puts a recovery session in the URL; wait for it before allowing a new password.
  form.querySelector("button[type=submit]").disabled = true;
  supabase?.auth.onAuthStateChange((evt) => {
    if (evt === "PASSWORD_RECOVERY") form.querySelector("button[type=submit]").disabled = false;
  });
}

form?.addEventListener("submit", async (e) => {
  e.preventDefault(); clearError();
  if (!configured) return;
  const v = Object.fromEntries(new FormData(form));
  const btn = form.querySelector("button[type=submit]");

  if (mode !== "reset-password" && !validEmail(v.email || "")) return showError("Enter a valid email address.");
  if ((mode === "register" || mode === "reset-password") && (v.password || "").length < 8)
    return showError("Password must be at least 8 characters.");
  if ((mode === "register" || mode === "reset-password") && v.password !== v.confirm)
    return showError("Passwords do not match.");
  if (mode === "register" && !(v.full_name || "").trim()) return showError("Enter your name.");

  await withBusy(btn, async () => {
    try {
      if (mode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email: v.email, password: v.password });
        if (error) throw error;
        location.href = safeNext;
      } else if (mode === "register") {
        const { data, error } = await supabase.auth.signUp({
          email: v.email, password: v.password,
          options: { data: { full_name: v.full_name.trim() }, emailRedirectTo: `${location.origin}/login` },
        });
        if (error) throw error;
        if (data.session) location.href = "/overview";
        else toast("Account created. Check your email to confirm, then sign in.", "success");
      } else if (mode === "forgot-password") {
        const { error } = await supabase.auth.resetPasswordForEmail(v.email, { redirectTo: `${location.origin}/reset-password` });
        if (error) throw error;
        toast("If that email has an account, a reset link is on its way.", "success");
      } else if (mode === "reset-password") {
        const { error } = await supabase.auth.updateUser({ password: v.password });
        if (error) throw error;
        toast("Password updated. Redirecting…", "success");
        setTimeout(() => (location.href = "/overview"), 1200);
      }
    } catch (err) {
      showError(err.message || "Something went wrong. Please try again.");
    }
  });
});
