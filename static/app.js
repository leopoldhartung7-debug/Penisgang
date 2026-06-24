(() => {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  const state = {
    platform: "discord",
    authToken: localStorage.getItem("authToken") || "",
  };

  // ─── tabs ────────────────────────────────────────────────
  $$(".tab").forEach((t) => {
    t.addEventListener("click", () => {
      $$(".tab").forEach((x) => x.classList.remove("active"));
      $$(".pane").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      $(`[data-pane="${t.dataset.tab}"]`).classList.add("active");
    });
  });

  // ─── log ─────────────────────────────────────────────────
  const logEl = $("#log");
  const ts = () => new Date().toTimeString().slice(0, 8);
  function log(msg, kind = "info") {
    const div = document.createElement("div");
    div.className = `line ${kind}`;
    div.innerHTML = `<span class="ts">${ts()}</span>${msg}`;
    logEl.prepend(div);
    while (logEl.childElementCount > 200) logEl.lastChild.remove();
  }
  $("#log-clear").addEventListener("click", () => (logEl.innerHTML = ""));

  // ─── auth header helper ──────────────────────────────────
  function authHeaders() {
    return state.authToken ? { "X-Auth-Token": state.authToken } : {};
  }
  $("#auth-token").value = state.authToken;
  $("#auth-save").addEventListener("click", () => {
    state.authToken = $("#auth-token").value.trim();
    localStorage.setItem("authToken", state.authToken);
    log("auth token gespeichert (lokal)", "ok");
  });

  // ─── status + platform buttons ───────────────────────────
  async function loadStatus() {
    try {
      const r = await fetch("/api/status").then((r) => r.json());
      $("#status-dot").classList.toggle("on", true);
      $("#status-dot").classList.toggle("off", false);
      $("#status-text").textContent = `${r.platforms.length} platforms · ${r.proxies} proxies · webhook ${r.webhook_enabled ? "an" : "aus"}`;
      buildPlatforms(r.platforms);
    } catch (e) {
      $("#status-text").textContent = "offline";
      log("server nicht erreichbar", "err");
    }
  }
  function buildPlatforms(list) {
    const wrap = $("#platforms");
    wrap.innerHTML = "";
    const items = [...list, "all"];
    items.forEach((p) => {
      const b = document.createElement("button");
      b.className = "plat-btn" + (p === state.platform ? " active" : "");
      b.textContent = p;
      b.addEventListener("click", () => {
        state.platform = p;
        $$(".plat-btn").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
      });
      wrap.appendChild(b);
    });
  }

  // ─── generate ────────────────────────────────────────────
  $("#generate-btn").addEventListener("click", async () => {
    const amount = parseInt($("#amount").value || "1", 10);
    log(`→ generate ${amount}× ${state.platform}`);
    try {
      const r = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ platform: state.platform, amount }),
      });
      const d = await r.json();
      if (!r.ok) return log(`generate fail: ${d.detail || r.status}`, "err");
      log(`queued ${d.queued} jobs`, "ok");
    } catch (e) {
      log(`network: ${e.message}`, "err");
    }
  });

  // ─── webhook ─────────────────────────────────────────────
  $("#wh-save").addEventListener("click", async () => {
    const url = $("#wh-url").value.trim();
    const enabled = $("#wh-enabled").checked;
    try {
      const r = await fetch("/api/webhook", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ url, enabled }),
      });
      const d = await r.json();
      if (!r.ok) return log(`webhook fail: ${d.detail || r.status}`, "err");
      log(`webhook ${d.enabled ? "aktiviert" : "deaktiviert"}`, "ok");
      loadStatus();
    } catch (e) {
      log(`network: ${e.message}`, "err");
    }
  });

  // ─── checker ─────────────────────────────────────────────
  $("#check-btn").addEventListener("click", async () => {
    const tokens = $("#check-tokens").value.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!tokens.length) return log("keine tokens", "warn");
    log(`→ prüfe ${tokens.length} tokens`);
    const r = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ tokens }),
    });
    const d = await r.json();
    if (!r.ok) return log(`check fail: ${d.detail || r.status}`, "err");
    log(`queued ${d.queued} checks`, "ok");
  });

  // ─── joiner ──────────────────────────────────────────────
  $("#join-btn").addEventListener("click", async () => {
    const invite = $("#join-invite").value.trim();
    const delay_ms = parseInt($("#join-delay").value || "800", 10);
    const tokens = $("#join-tokens").value.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!invite || !tokens.length) return log("invite + tokens fehlen", "warn");
    log(`→ joine ${tokens.length} tokens → ${invite}`);
    const r = await fetch("/api/join", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ tokens, invite, delay_ms }),
    });
    const d = await r.json();
    if (!r.ok) return log(`join fail: ${d.detail || r.status}`, "err");
    log(`queued ${d.queued} joins`, "ok");
  });

  // ─── SSE event stream ────────────────────────────────────
  function connectEvents() {
    const es = new EventSource("/api/events");
    es.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data);
        if (ev.kind === "account") log(`✓ ${ev.platform} · ${ev.username} · ${ev.email}`, "ok");
        else if (ev.kind === "log") log(ev.message, "info");
        else if (ev.kind === "check") log(`check · ${ev.token} · ${ev.valid ? "VALID" : "invalid"}${ev.reason ? " · " + ev.reason : ""}`, ev.valid ? "ok" : "warn");
        else if (ev.kind === "join") log(`join · ${ev.token} · ${ev.success ? "JOINED" : "failed"}${ev.reason ? " · " + ev.reason : ""}`, ev.success ? "ok" : "err");
        else if (ev.kind === "webhook") log(`webhook ${ev.enabled ? "an" : "aus"}`, "info");
      } catch (_) {}
    };
    es.onerror = () => {
      log("event stream lost, reconnect in 3s", "warn");
      es.close();
      setTimeout(connectEvents, 3000);
    };
  }

  loadStatus();
  connectEvents();
})();
