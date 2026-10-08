// Phase 5: dashboard "Received files" (relay to outbox) and "Transfer
// history". Diffed in place (list-diff.js) so a 5s refresh doesn't flicker
// or reset scroll position, and doesn't reset an in-flight "Sending..."
// button back to its default label.
(function () {
  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    const units = ["KB", "MB", "GB", "TB"];
    let value = bytes;
    let unit = -1;
    do {
      value /= 1024;
      unit += 1;
    } while (value >= 1024 && unit < units.length - 1);
    return `${value.toFixed(1)} ${units[unit]}`;
  }

  function timeAgo(epochSeconds) {
    const seconds = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  }

  function createReceivedEl(f) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="file-row">
        <span class="name"></span>
        <span class="meta"></span>
        <div class="actions">
          <button class="secondary relay-btn">Send to phone</button>
        </div>
      </div>`;
    const btn = li.querySelector(".relay-btn");
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "Sending...";
      try {
        await fetch(`/api/library/relay?filename=${encodeURIComponent(f.filename)}`, { method: "POST" });
        btn.textContent = "Sent";
      } catch (e) {
        btn.textContent = "Failed - retry";
        btn.disabled = false;
      }
    });
    updateReceivedEl(li, f);
    return li;
  }

  function updateReceivedEl(li, f) {
    li.querySelector(".name").textContent = f.filename;
    li.querySelector(".meta").textContent = formatBytes(f.size);
  }

  async function refreshReceived() {
    const list = document.getElementById("received-list");
    if (!list) return;
    let files;
    try {
      files = await (await fetch("/api/library/received")).json();
    } catch (e) {
      return;
    }
    window.NDListDiff.renderDiffList(
      list,
      files,
      (f) => f.filename,
      createReceivedEl,
      updateReceivedEl,
      '<li class="muted">Nothing received yet.</li>'
    );
  }

  function createHistoryEl(r) {
    const li = document.createElement("li");
    li.innerHTML = `<div class="file-row"><span class="name"></span><span class="meta"></span></div>`;
    updateHistoryEl(li, r);
    return li;
  }

  function updateHistoryEl(li, r) {
    const arrow = r.direction === "upload" ? "→ laptop" : "→ phone";
    li.querySelector(".name").innerHTML = `${r.filename} <span class="meta">(${arrow})</span>`;
    li.querySelector(".meta").textContent = `${formatBytes(r.size)} - ${r.device} - ${timeAgo(r.timestamp)}`;
  }

  async function refreshHistory() {
    const list = document.getElementById("history-list");
    if (!list) return;
    let rows;
    try {
      rows = await (await fetch("/api/history")).json();
    } catch (e) {
      return;
    }
    window.NDListDiff.renderDiffList(
      list,
      rows,
      (r) => `${r.direction}:${r.filename}:${r.timestamp}`,
      createHistoryEl,
      updateHistoryEl,
      '<li class="muted">No transfers yet.</li>'
    );
  }

  refreshReceived();
  refreshHistory();
  setInterval(refreshReceived, 5000);
  setInterval(refreshHistory, 5000);
})();
