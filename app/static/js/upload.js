// Phase 2 mobile "Send to laptop" tab - UI rows wired to ChunkedUploader.
(function () {
  function deviceLabel() {
    const ua = navigator.userAgent || "device";
    if (/iPhone/.test(ua)) return "iPhone";
    if (/iPad/.test(ua)) return "iPad";
    if (/Android/.test(ua)) return "Android phone";
    return "Phone";
  }

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

  function formatSpeed(bytesPerSec) {
    if (!bytesPerSec || !isFinite(bytesPerSec)) return "";
    return `${formatBytes(bytesPerSec)}/s`;
  }

  class UploadRow {
    constructor(file, container) {
      this.file = file;
      this.cancelState = { cancelled: false, controllers: new Set() };
      this.el = document.createElement("li");
      this.el.innerHTML = `
        <div class="file-row">
          <span class="name">${file.name}</span>
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
      this.cancelBtn.addEventListener("click", () => {
        this.cancelState.cancelled = true;
        this.cancelState.controllers.forEach((c) => c.abort());
      });
    }

    setProgress(sentBytes, totalBytes, speed) {
      const pct = totalBytes > 0 ? Math.min(100, (sentBytes / totalBytes) * 100) : 100;
      this.fill.style.width = `${pct}%`;
      this.statusText.textContent =
        `${formatBytes(sentBytes)} / ${formatBytes(totalBytes)}` + (speed ? ` - ${formatSpeed(speed)}` : "");
    }

    setDone() {
      this.fill.style.width = "100%";
      this.fill.classList.add("done");
      this.statusText.textContent = `${formatBytes(this.file.size)} - done`;
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

  async function runUpload(file, row) {
    row.cancelState = { cancelled: false, controllers: new Set() };
    try {
      await window.ChunkedUploader.send(file, {
        endpointBase: "/api/upload",
        device: deviceLabel(),
        storagePrefix: "nd-upload",
        cancelState: row.cancelState,
        onProgress: (sent, total, speed) => row.setProgress(sent, total, speed),
      });
      row.setDone();
    } catch (err) {
      if (err.cancelled) {
        row.setCancelled();
      } else {
        row.setError("Upload failed - tap Retry", () => runUpload(file, row));
      }
    }
  }

  function initUploadUI() {
    const dropzone = document.getElementById("dropzone");
    const input = document.getElementById("file-input");
    const list = document.getElementById("upload-list");
    if (!dropzone || !input || !list) return;

    dropzone.addEventListener("click", () => input.click());
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer && e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
    });
    input.addEventListener("change", () => {
      if (input.files.length) handleFiles(input.files);
      input.value = "";
    });

    function handleFiles(fileList) {
      Array.from(fileList).forEach((file) => {
        const row = new UploadRow(file, list);
        runUpload(file, row);
      });
    }
  }

  window.NaharDropUpload = { initUploadUI };
  document.addEventListener("DOMContentLoaded", initUploadUI);
})();
