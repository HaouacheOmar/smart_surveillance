// Tokens live in HttpOnly cookies; JS only ever sees the CSRF token.
const csrf = () => document.cookie.match(/(?:^|; )csrftoken=([^;]*)/)?.[1] ?? "";

let refreshing = null; // single in-flight refresh: rotated refresh tokens are single-use

function refresh() {
  refreshing ??= fetch("/api/auth/refresh/", { method: "POST", headers: { "X-CSRFToken": csrf() } })
    .then((r) => r.ok)
    .finally(() => (refreshing = null));
  return refreshing;
}

export async function api(path, { method = "GET", body, raw } = {}, retry = true) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { "X-CSRFToken": csrf(), ...(body && { "Content-Type": "application/json" }) },
    body: body && JSON.stringify(body),
  });
  if (res.status === 401 && retry && !/^\/auth\/(login|refresh|logout)/.test(path)) {
    if (await refresh()) return api(path, { method, body, raw }, false);
    window.dispatchEvent(new Event("logout"));
  }
  if (!res.ok) {
    const err = new Error((await res.text()) || res.statusText);
    err.status = res.status;
    throw err;
  }
  if (raw) return res.blob();
  return res.status === 204 ? null : res.json();
}
