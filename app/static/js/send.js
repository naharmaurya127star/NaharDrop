// Phase 3 dashboard "Send files to your phone" drop zone: supports both
// flat file drops and whole-folder drops (via the Chromium/Edge/Firefox
// webkitGetAsEntry directory-traversal API), ingesting each file through the
// shared chunked uploader against /api/send, which files it into the outbox
// the phone's Receive tab polls.
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

  function readAllEntries(reader) {
    return new Promise((resolve, reject) => {
      let all = [];
      function readBatch() {
        reader.readEntries((entries) => {
          if (!entries.length) {
            resolve(all);
            return;
          }
          all = all.concat(entries);
          readBatch();
        }, reject);
      }
      readBatch();
    });
  }

  // Walks a dropped DataTransferItem's FileSystemEntry tree, collecting
  // {file, relDir, group} for every leaf file. `group` is the top-level
  // folder name shared by every file under it, used server-side to group
  // the outbox listing and to build the on-the-fly folder zip.
  async function collectEntry(entry, parentPath, group, out) {
    if (entry.isFile) {
      const file = await new Promise((resolve, reject) => entry.file(resolve, reject));
      out.push({ file, relDir: parentPath, group });
    } else if (entry.isDirectory) {
      const nextPath = parentPath ? `${parentPath}/${entry.name}` : entry.name;
      const nextGroup = group || entry.name;
      const reader = entry.createReader();
      const entries = await readAllEntries(reader);
      for (const child of entries) {
        await collectEntry(child, nextPath, nextGroup, out);
      }
    }
  }

  async function collectDrop(dataTransfer) {
    const items = Array.from(dataTransfer.items || []);
    const out = [];
    const supportsEntries = items.length > 0 && typeof items[0].webkitGetAsEntry === "function";
    if (supportsEntries) {
      for (const item of items) {
        const entry = item.webkitGetAsEntry && item.webkitGetAsEntry();
        if (entry) await collectEntry(entry, "", null, out);
      }
    } else {
      Array.from(dataTransfer.files || []).forEach((file) => out.push({ file, relDir: "", group: null }));
    }
    return out;
  }

  class SendRow {
    constructor(label, container) {
      this.el = document.createElement("li");
      this.el.innerHTML = `
        <div class="file-row">
          <span class="name">${label}</span>
          <div class="progress-track"><div class="progress-fill"></div></div>
          <span class="meta"><span class="status-text">Waiting...</span></span>
          <div class="actions">
            <button class="secondary cancel-btn">Cancel</button>
            <button class="retry-btn" hidden>Retry</button>
          </div>
        </div>`;
      container.appendChild(this.el);
      this.fill = this.el.querySelector(".progress-fill");
      this.statusText = this.el.querySelector(".status-text");
      this.cancelBtn = this.el.querySelector(".cancel-btn");
      this.retryBtn = this.el.querySelector(".retry-btn");
      this.cancelState = { cancelled: false, controllers: new Set() };
      this.cancelBtn.addEventListener("click", () => {
        this.cancelState.cancelled = true;
        this.cancelState.controllers.forEach((c) => c.abort());
      });
    }

    setProgress(sentBytes, totalBytes, speed) {
      const pct = totalBytes > 0 ? Math.min(100, (sentBytes / totalBytes) * 100) : 100;
      this.fill.style.width = `${pct}%`;
      const speedText = speed && isFinite(speed) ? ` - ${formatBytes(speed)}/s` : "";
      this.statusText.textContent = `${formatBytes(sentBytes)} / ${formatBytes(totalBytes)}${speedText}`;
    }

    setDone(totalBytes) {
      this.fill.style.width = "100%";
      this.fill.classList.add("done");
      this.statusText.textContent = `${formatBytes(totalBytes)} - sent`;
      this.cancelBtn.hidden = true;
    }

    setError(message, onRetry) {
      this.fill.classList.add("error");
      this.statusText.textContent = message;
      this.retryBtn.hidden = false;
      this.retryBtn.onclick = () => {
        this.fill.classList.remove("error");
        this.retryBtn.hidden = true;
        onRetry();
      };
    }

    setCancelled() {
      this.statusText.textContent = "Cancelled";
      this.cancelBtn.hidden = true;
    }
  }

  async function sendOne(entry, row) {
    row.cancelState = { cancelled: false, controllers: new Set() };
    try {
      await window.ChunkedUploader.send(entry.file, {
        endpointBase: "/api/send",
        relDir: entry.relDir,
        group: entry.group,
        storagePrefix: "nd-send",
        cancelState: row.cancelState,
        onProgress: (sent, total, speed) => row.setProgress(sent, total, speed),
      });
      row.setDone(entry.file.size);
    } catch (err) {
      if (err.cancelled) {
        row.setCancelled();
      } else {
        row.setError("Send failed - tap Retry", () => sendOne(entry, row));
      }
    }
  }

  function initSendUI() {
    const dropzone = document.getElementById("dropzone");
    const input = document.getElementById("file-input");
    const list = document.getElementById("send-list");
    if (!dropzone || !input || !list) return;

    dropzone.addEventListener("click", () => input.click());
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", async (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (!e.dataTransfer) return;
      const entries = await collectDrop(e.dataTransfer);
      queueEntries(entries);
    });
    input.addEventListener("change", () => {
      const entries = Array.from(input.files).map((file) => ({ file, relDir: "", group: null }));
      queueEntries(entries);
      input.value = "";
    });

    function queueEntries(entries) {
      entries.forEach((entry) => {
        const label = entry.relDir ? `${entry.relDir}/${entry.file.name}` : entry.file.name;
        const row = new SendRow(label, list);
        sendOne(entry, row);
      });
    }
  }

  document.addEventListener("DOMContentLoaded", initSendUI);
})();
