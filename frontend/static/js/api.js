// Thin fetch wrapper: attaches the user's access token, normalises errors.
import { supabase } from "./supabase-client.js";

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function accessToken() {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function api(path, { method = "GET", body, form, signal } = {}) {
  const headers = {};
  const token = await accessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  let res;
  try { res = await fetch(`/api${path}`, { method, headers, body: payload, signal }); }
  catch { throw new ApiError("Cannot reach the CivicScope server. Check your connection.", 0); }
  if (res.status === 401 && !location.pathname.match(/^\/(login|register|forgot-password|reset-password)/)) {
    location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
  }
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) {
    const detail = data?.detail;
    const msg = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map(d => d.msg).join("; ") : "Request failed.";
    throw new ApiError(msg, res.status);
  }
  return data;
}

// Authenticated file download (a plain <a href> cannot send the Bearer token).
export async function apiDownload(path, fallbackName = "download") {
  const token = await accessToken();
  const res = await fetch(`/api${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError("The download failed.", res.status);
  const m = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") || "");
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: m ? m[1] : fallbackName });
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}
