// Phase 4: pairing gate shown on the phone before it can use the main UI.
// Two entry paths: scanning the QR (URL carries ?t=<qr_token>, auto-pairs)
// or typing the dashboard URL manually (must enter the PIN shown there).
// Either way the laptop must still approve the device before it gets a
// session cookie.
(function () {
  function deviceLabel() {
    const ua = navigator.userAgent || "device";
    if (/iPhone/.test(ua)) return "iPhone";
    if (/iPad/.test(ua)) return "iPad";
    if (/Android/.test(ua)) return "Android phone";
    return "Phone";
  }

  function showMainUI() {
    document.getElementById("pairing-gate").hidden = true;
    document.getElementById("main-ui").hidden = false;
  }

  function showGateState(name) {
    ["pair-pin-form", "pair-waiting", "pair-denied"].forEach((id) => {
      document.getElementById(id).hidden = id !== name;
    });
  }

  async function pollStatus(pendingToken) {
    try {
      const resp = await fetch(`/api/auth/pair-status/${pendingToken}`);
      const data = await resp.json();
      if (data.status === "approved") {
        showMainUI();
        return;
      }
      if (data.status === "denied") {
        showGateState("pair-denied");
        return;
      }
    } catch (e) {
      /* network hiccup - keep polling */
    }
    setTimeout(() => pollStatus(pendingToken), 1500);
  }

  async function submitPair(body) {
    const resp = await fetch("/api/auth/pair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({ detail: "Pairing failed" }));
      throw new Error(data.detail || "Pairing failed");
    }
    const data = await resp.json();
    showGateState("pair-waiting");
    pollStatus(data.pending_token);
  }

  async function init() {
    let config;
    try {
      config = await (await fetch("/api/auth/config")).json();
    } catch (e) {
      config = { require_pin: false };
    }

    if (!config.require_pin) {
      showMainUI();
      return;
    }

    document.getElementById("pairing-gate").hidden = false;
    const params = new URLSearchParams(location.search);
    const qrToken = params.get("t");

    if (qrToken) {
      showGateState("pair-waiting");
      try {
        await submitPair({ token: qrToken, device_name: deviceLabel() });
      } catch (err) {
        showGateState("pair-denied");
      }
      return;
    }

    showGateState("pair-pin-form");
    document.getElementById("pair-submit-btn").addEventListener("click", async () => {
      const pin = document.getElementById("pair-pin-input").value.trim();
      const name = document.getElementById("pair-device-name").value.trim() || deviceLabel();
      document.getElementById("pair-error").textContent = "";
      try {
        await submitPair({ pin, device_name: name });
      } catch (err) {
        document.getElementById("pair-error").textContent = err.message;
      }
    });

    document.getElementById("pair-retry-btn").addEventListener("click", () => showGateState("pair-pin-form"));
  }

  document.addEventListener("DOMContentLoaded", init);
})();
