// Phase 4: pending-device approval (pushed live over WebSocket, with a
// polling fallback) and the connected-devices list. Lists are diffed in
// place (list-diff.js) rather than replaced wholesale, so they don't flicker
// on every refresh.
(function () {
  const pendingCard = document.getElementById("pending-card");
  const pendingList = document.getElementById("pending-list");
  const deviceList = document.getElementById("device-list");
  if (!pendingList || !deviceList) return; // require_pin is off, nothing to do

  function timeAgo(epochSeconds) {
    const seconds = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
    if (seconds < 60) return `${seconds}s ago`;
    return `${Math.floor(seconds / 60)}m ago`;
  }

  function createPendingEl(item) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="file-row">
        <span class="name"></span>
        <div class="actions">
          <button class="approve-btn">Approve</button>
          <button class="secondary deny-btn">Deny</button>
        </div>
      </div>`;
    li.querySelector(".approve-btn").addEventListener("click", async () => {
      await fetch(`/api/auth/approve/${item.token}`, { method: "POST" });
      refreshPending();
      refreshSessions();
    });
    li.querySelector(".deny-btn").addEventListener("click", async () => {
      await fetch(`/api/auth/deny/${item.token}`, { method: "POST" });
      refreshPending();
    });
    updatePendingEl(li, item);
    return li;
  }

  function updatePendingEl(li, item) {
    li.querySelector(".name").textContent = item.device_name;
  }

  function renderPending(items) {
    pendingCard.hidden = items.length === 0;
    window.NDListDiff.renderDiffList(pendingList, items, (i) => i.token, createPendingEl, updatePendingEl, "");
  }

  function createSessionEl(s) {
    const li = document.createElement("li");
    li.innerHTML = `<div class="file-row"><span class="name"></span><span class="meta"></span></div>`;
    updateSessionEl(li, s);
    return li;
  }

  function updateSessionEl(li, s) {
    li.querySelector(".name").textContent = s.device_name;
    li.querySelector(".meta").textContent = `last seen ${timeAgo(s.last_seen)}`;
  }

  function renderSessions(sessions) {
    window.NDListDiff.renderDiffList(
      deviceList,
      sessions,
      (s) => s.device_name,
      createSessionEl,
      updateSessionEl,
      '<li class="muted">No devices connected yet.</li>'
    );
  }

  async function refreshPending() {
    try {
      renderPending(await (await fetch("/api/auth/pending")).json());
    } catch (e) {
      /* ignore */
    }
  }

  async function refreshSessions() {
    try {
      renderSessions(await (await fetch("/api/auth/sessions")).json());
    } catch (e) {
      /* ignore */
    }
  }

  function connectWS() {
    const proto = location.protocol === "https:" ? "wss://" : "ws://";
    const ws = new WebSocket(`${proto}${location.host}/api/auth/ws/dashboard`);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "pending_device" || msg.type === "device_approved") {
        refreshPending();
        refreshSessions();
      }
    };
    ws.onclose = () => setTimeout(connectWS, 2000);
  }

  refreshPending();
  refreshSessions();
  // last-seen timestamps still need to tick forward even with no WS event
  setInterval(refreshSessions, 10000);
  connectWS();
})();
