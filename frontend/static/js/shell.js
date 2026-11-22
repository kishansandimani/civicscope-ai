// Shared shell for every app page: auth guard, nav wiring, real profile data, sign-out, notifications badge.
import { supabase, configured } from "./supabase-client.js";
import { api } from "./api.js";
import { toast } from "./ui.js";
import { initVoice } from "./voice.js";
import { wireHeader, syncHeader } from "./header.js";

const PLACEHOLDER_NAME = "Dr. Maya Rao";
const PLACEHOLDER_ROLE = "Senior Analyst";

function replaceText(root, from, to) {
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const hits = [];
  while (w.nextNode()) if (w.currentNode.nodeValue.includes(from)) hits.push(w.currentNode);
  hits.forEach(n => (n.nodeValue = n.nodeValue.replace(from, to)));
}

function wireNavigation(current) {
  document.querySelectorAll("a[data-path]").forEach(a => {
    a.setAttribute("href", `/${a.dataset.path}`);
    if (a.dataset.path === current) a.setAttribute("aria-current", "page");
  });
}

function wireSignOut() {
  document.querySelectorAll("button").forEach(b => {
    if (/sign out/i.test(b.textContent)) {
      b.addEventListener("click", async () => {
        await supabase?.auth.signOut();
        location.href = "/login";
      });
    }
  });
}

async function loadProfile() {
  try {
    const me = await api("/me");
    const name = me.full_name || me.email || "Account";
    replaceText(document.body, PLACEHOLDER_NAME, name);
    replaceText(document.body, PLACEHOLDER_ROLE, me.designation || me.email || "");
    document.querySelectorAll(`img[alt^="${PLACEHOLDER_NAME}"]`).forEach(img => {
      img.alt = `${name} profile`;
    });
    window.civic = { ...(window.civic || {}), me };
    document.dispatchEvent(new CustomEvent("civic:ready", { detail: { me } }));
  } catch (e) { toast(e.message, "error"); }
}

async function loadNotificationsBadge() {
  try {
    const { unread } = await api("/notifications");
    const btn = document.querySelector('button[title="Governance Alerts"]');
    const dot = btn?.querySelector("span.absolute");
    if (dot) dot.style.display = unread > 0 ? "" : "none";
    if (btn) btn.setAttribute("aria-label", unread ? `${unread} unread notifications` : "No unread notifications");
  } catch { /* non-critical */ }
}

async function init() {
  const page = document.body.dataset.page;
  wireNavigation(page);
  if (!configured) {
    toast("Supabase is not configured on the server. Copy backend/.env.example to backend/.env and fill it in.", "error");
    return;
  }
  const { data } = await supabase.auth.getSession();
  if (!data.session) { location.href = `/login?next=${encodeURIComponent(location.pathname)}`; return; }
  supabase.auth.onAuthStateChange((evt) => { if (evt === "SIGNED_OUT") location.href = "/login"; });
  wireSignOut();
  await loadProfile();
  loadNotificationsBadge();
  wireHeader();
  await initVoice();
  syncHeader();
  document.addEventListener("civic:voice-state", syncHeader);
}

init();
