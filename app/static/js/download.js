// Phase 3 mobile "Receive from laptop" tab, revised to avoid the flicker a
// naive 2s poll + full re-render caused: the outbox list is diffed in place
// (see list-diff.js) so unrelated rows - including an in-progress <video> -
// are never torn down, and updates arrive via a WebSocket push instead of a
// tight poll, with a slow poll kept only as a fallback while disconnected.
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

  const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|svg)$/i;
  const VIDEO_EXT = /\.(mp4|webm|mov|m4v|ogg)$/i;

  // Generic placeholder poster so preload="none" videos show a frame
  // instead of a blank box before the user taps play - no network request,
  // no server-side thumbnail generation needed.
  const VIDEO_POSTER =
    "data:image/svg+xml;charset=UTF-8," +
    encodeURIComponent(
      `<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180'>` +
        `<rect width='100%' height='100%' fill='#20242b'/>` +
        `<polygon points='132,62 132,118 190,90' fill='#9aa1ab'/></svg>`
    );

  function previewMarkup(itemId, name) {
    const src = `/api/outbox/file/${itemId}/preview`;
    if (IMAGE_EXT.test(name)) return `<img class="preview-media" src="${src}" alt="${name}" loading="lazy">`;
    if (VIDEO_EXT.test(name))
      return `<video class="preview-media" src="${src}" controls preload="none" poster="${VIDEO_POSTER}"></video>`;
    return "";
  }

  function createFolderEl(folder) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="file-row">
        <span class="name folder-name"></span>
        <span class="meta folder-meta"></span>
        <div class="actions">
          <a class="btn folder-zip-link" href="/api/outbox/folder/${encodeURIComponent(folder.group)}/zip">Download ZIP</a>
        </div>
      </div>`;
    updateFolderEl(li, folder);
    return li;
  }

  function updateFolderEl(li, folder) {
    li.querySelector(".folder-name").textContent = `${folder.group}/ (${folder.count} files)`;
    li.querySelector(".folder-meta").textContent = formatBytes(folder.size);
  }

  function createFileEl(file) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="file-row">
        <span class="name"></span>
        <span class="meta"></span>
        ${previewMarkup(file.item_id, file.name)}
        <div class="actions">
          <a class="btn" href="/api/outbox/file/${file.item_id}" download="${file.name}">Download</a>
        </div>
      </div>`;
    updateFileEl(li, file);
    return li;
  }

  function updateFileEl(li, file) {
    // Name/size are immutable once a file lands in the outbox, so this is
    // effectively a no-op after creation - but keeping it means an existing
    // <video>/<img> element is never recreated just because the surrounding
    // row got touched during a diff pass.
    li.querySelector(".name").textContent = file.name;
    li.querySelector(".meta").textContent = formatBytes(file.size);
  }

  function render(list, data) {
    const folderItems = data.folders.map((f) => ({ ...f, _key: `folder:${f.group}` }));
    const fileItems = data.files.map((f) => ({ ...f, _key: `file:${f.item_id}` }));
    const all = [...folderItems, ...fileItems];

    window.NDListDiff.renderDiffList(
      list,
      all,
      (item) => item._key,
      (item) => (item._key.startsWith("folder:") ? createFolderEl(item) : createFileEl(item)),
      (el, item) => (item._key.startsWith("folder:") ? updateFolderEl(el, item) : updateFileEl(el, item)),
      '<li class="muted">Nothing shared yet.</li>'
    );
  }

  async function refresh(list) {
    try {
      const resp = await fetch("/api/outbox");
      if (!resp.ok) return;
      render(list, await resp.json());
    } catch (e) {
      /* network hiccup - next poll/push will retry */
    }
  }

  function connectWS(list) {
    let wsConnected = false;
    const proto = location.protocol === "https:" ? "wss://" : "ws://";

    function connect() {
      let ws;
      try {
        ws = new WebSocket(`${proto}${location.host}/ws/outbox`);
      } catch (e) {
        setTimeout(connect, 3000);
        return;
      }
      ws.onopen = () => {
        wsConnected = true;
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "outbox_changed") refresh(list);
        } catch (e) {
          /* ignore malformed push */
        }
      };
      ws.onclose = () => {
        wsConnected = false;
        setTimeout(connect, 3000);
      };
      ws.onerror = () => {
        wsConnected = false;
      };
    }
    connect();

    // Fallback poll: a no-op whenever the push channel is up, so this only
    // actually refreshes anything while the WebSocket is disconnected.
    setInterval(() => {
      if (!wsConnected) refresh(list);
    }, 7000);
  }

  function initDownloadUI() {
    const list = document.getElementById("incoming-list");
    if (!list) return;
    refresh(list);
    connectWS(list);
  }

  document.addEventListener("DOMContentLoaded", initDownloadUI);
})();
