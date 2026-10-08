// Shared chunked-upload engine used by both the phone "send to laptop" page
// (against /api/upload) and the laptop dashboard "send to phone" drop zone
// (against /api/send). Handles chunking, bounded concurrency, per-chunk
// retry with backoff, cancellation, and resume-after-reconnect by asking the
// server which chunk indices are still missing.
window.ChunkedUploader = (function () {
  const MAX_RETRIES = 5;

  function fileKey(prefix, file) {
    return `${prefix}:${file.name}:${file.size}:${file.lastModified}`;
  }

  function storageGet(key) {
    try {
      const raw = sessionStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function storageSet(key, value) {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      /* ignore - resume-after-reload just won't work this time */
    }
  }

  function storageClear(key) {
    try {
      sessionStorage.removeItem(key);
    } catch (e) {
      /* ignore */
    }
  }

  async function jsonFetch(url, options) {
    const resp = await fetch(url, options);
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(`${resp.status} ${text}`);
    }
    return resp.json();
  }

  async function uploadChunkWithRetry(endpointBase, uploadId, index, blob, controllers, isCancelled) {
    let attempt = 0;
    while (true) {
      if (isCancelled()) throw new Error("cancelled");
      const controller = new AbortController();
      controllers.add(controller);
      try {
        const resp = await fetch(`${endpointBase}/${uploadId}/chunk/${index}`, {
          method: "PUT",
          body: blob,
          headers: { "Content-Type": "application/octet-stream" },
          signal: controller.signal,
        });
        if (!resp.ok) throw new Error(`chunk ${index} failed: ${resp.status}`);
        return;
      } catch (err) {
        if (isCancelled()) throw new Error("cancelled");
        attempt += 1;
        if (attempt > MAX_RETRIES) throw err;
        await new Promise((r) => setTimeout(r, Math.min(8000, 500 * 2 ** attempt)));
      } finally {
        controllers.delete(controller);
      }
    }
  }

  /**
   * Upload `file` in chunks to `endpointBase` (e.g. "/api/upload" or "/api/send").
   * options: { chunkSize, concurrency, relDir, group, device, storagePrefix,
   *            onProgress(sentBytes, totalBytes, speedOrNull), isCancelledRef }
   * `isCancelledRef` is an object with a `.cancelled` boolean the caller can flip,
   * and `.controllers` (a Set) the caller can use to abort in-flight requests directly.
   * Returns the parsed response of the final /complete call.
   */
  async function send(file, options) {
    const {
      endpointBase,
      chunkSize = 5 * 1024 * 1024,
      concurrency = 3,
      relDir = "",
      group = null,
      device = "",
      storagePrefix = "nd",
      onProgress = () => {},
      cancelState,
    } = options;

    const state = cancelState || { cancelled: false, controllers: new Set() };
    const isCancelled = () => state.cancelled;
    const key = fileKey(storagePrefix, file);

    let record = storageGet(key);
    let uploadId, actualChunkSize, totalChunks, missing;

    if (record) {
      try {
        const status = await jsonFetch(`${endpointBase}/${record.uploadId}/status`);
        uploadId = record.uploadId;
        actualChunkSize = record.chunkSize;
        totalChunks = status.total_chunks;
        missing = status.missing;
      } catch (e) {
        record = null;
      }
    }

    if (!record) {
      const init = await jsonFetch(`${endpointBase}/init`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: file.name,
          size: file.size,
          chunk_size: chunkSize,
          device,
          rel_dir: relDir,
          group,
        }),
      });
      uploadId = init.upload_id;
      actualChunkSize = init.chunk_size;
      totalChunks = init.total_chunks;
      missing = Array.from({ length: totalChunks }, (_, i) => i);
      storageSet(key, { uploadId, chunkSize: actualChunkSize });
    }

    let sentBytes = Math.min(file.size, (totalChunks - missing.length) * actualChunkSize);

    // Speed is exponentially smoothed (time-constant ~4s, so it settles over
    // roughly a 3-5s window) and the UI callback is throttled to at most
    // once/sec, so the displayed number doesn't jitter chunk-to-chunk.
    const SPEED_TAU = 4;
    const MIN_EMIT_INTERVAL_MS = 1000;
    let smoothedSpeed = null;
    let lastSampleTime = performance.now();
    let lastSampleBytes = sentBytes;
    let lastEmitTime = 0;

    function sampleAndMaybeEmit(currentBytes, force) {
      const now = performance.now();
      const dt = (now - lastSampleTime) / 1000;
      if (dt > 0.05) {
        const instant = (currentBytes - lastSampleBytes) / dt;
        smoothedSpeed =
          smoothedSpeed === null ? instant : smoothedSpeed + (1 - Math.exp(-dt / SPEED_TAU)) * (instant - smoothedSpeed);
        lastSampleTime = now;
        lastSampleBytes = currentBytes;
      }
      if (force || now - lastEmitTime >= MIN_EMIT_INTERVAL_MS) {
        onProgress(currentBytes, file.size, smoothedSpeed);
        lastEmitTime = now;
      }
    }

    sampleAndMaybeEmit(sentBytes, true);

    const queue = missing.slice();
    let firstError = null;

    async function worker() {
      while (queue.length > 0) {
        if (isCancelled()) return;
        const index = queue.shift();
        if (index === undefined) return;
        const start = index * actualChunkSize;
        const end = Math.min(file.size, start + actualChunkSize);
        const blob = file.slice(start, end);
        try {
          await uploadChunkWithRetry(endpointBase, uploadId, index, blob, state.controllers, isCancelled);
          sentBytes = Math.min(file.size, sentBytes + (end - start));
          sampleAndMaybeEmit(sentBytes, false);
        } catch (err) {
          if (!firstError) firstError = err;
        }
      }
    }

    const workerCount = Math.max(1, Math.min(concurrency, queue.length || 1));
    await Promise.all(Array.from({ length: workerCount }, worker));
    sampleAndMaybeEmit(sentBytes, true);

    if (isCancelled()) {
      await fetch(`${endpointBase}/${uploadId}`, { method: "DELETE" }).catch(() => {});
      storageClear(key);
      const err = new Error("cancelled");
      err.cancelled = true;
      throw err;
    }

    if (firstError) {
      throw firstError;
    }

    const completeUrl = group
      ? `${endpointBase}/${uploadId}/complete?group=${encodeURIComponent(group)}`
      : `${endpointBase}/${uploadId}/complete`;
    const done = await jsonFetch(completeUrl, { method: "POST" });
    storageClear(key);
    return done;
  }

  return { send, fileKey };
})();
