/**
 * Solaredge PV Export Limiter — custom Lovelace card.
 *
 * Self-contained, no build step, no external deps. Uses the LitElement
 * shipped with Home Assistant frontend. Auto-registered by the integration.
 */

const html = (strings, ...values) => {
  let s = "";
  strings.forEach((str, i) => (s += str + (values[i] ?? "")));
  return s;
};

const STATUS_CHIPS = {
  ok: { label: "Working", color: "#3eb049" },
  disabled: { label: "Disabled", color: "#888" },
  no_pv: { label: "No PV", color: "#778" },
  sensor_loss: { label: "Sensor lost", color: "#e8b500" },
  voltage_high: { label: "Voltage high", color: "#d9534f" },
  write_error: { label: "Write error", color: "#d9534f" },
  starting: { label: "Starting", color: "#5bc0de" },
};

class PVLimiterCard extends HTMLElement {
  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = config;
    this._entryPrefix = config.entry_prefix || "solaredge_pv_export_limiter";
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._rendered) {
      this._render();
      this._rendered = true;
    } else {
      this._update();
    }
  }

  getCardSize() {
    return 6;
  }

  _e(domain, name) {
    if (!this._hass) return null;
    const id = `${domain}.${this._entryPrefix}_${name}`;
    return this._hass.states[id];
  }

  _val(domain, name, fallback = "—") {
    const ent = this._e(domain, name);
    if (!ent || ent.state === "unknown" || ent.state === "unavailable") return fallback;
    return ent.state;
  }

  _render() {
    this.innerHTML = html`
      <ha-card style="padding: 16px;">
        <style>
          .pvlim-row { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 16px; }
          .pvlim-tile {
            flex: 1; min-width: 110px;
            background: var(--card-background-color, #fff);
            border: 1px solid var(--divider-color, #ccc);
            border-radius: 12px; padding: 12px; text-align: center;
          }
          .pvlim-tile .label { font-size: 12px; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.5px; }
          .pvlim-tile .value { font-size: 24px; font-weight: 600; margin-top: 6px; }
          .pvlim-tile .unit { font-size: 14px; font-weight: 400; color: var(--secondary-text-color); margin-left: 2px; }
          .pvlim-status-chip {
            display: inline-block; padding: 4px 10px; border-radius: 14px;
            color: white; font-weight: 500; font-size: 13px;
          }
          .pvlim-modes { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
          .pvlim-mode-btn {
            padding: 8px 14px; border-radius: 18px;
            background: var(--secondary-background-color, #eee);
            border: 1px solid transparent;
            cursor: pointer; font-size: 13px; transition: all .15s;
          }
          .pvlim-mode-btn.active {
            background: var(--primary-color, #03a9f4); color: white;
            border-color: var(--primary-color, #03a9f4);
          }
          .pvlim-gauge-wrap {
            display: flex; align-items: center; gap: 16px; margin-bottom: 12px;
          }
          .pvlim-gauge-bar {
            flex: 1; height: 12px; background: var(--secondary-background-color, #eee);
            border-radius: 6px; overflow: hidden; position: relative;
          }
          .pvlim-gauge-fill {
            height: 100%; transition: width .4s ease;
            background: linear-gradient(90deg, #d9534f 0%, #e8b500 50%, #3eb049 100%);
          }
          .pvlim-gauge-target {
            position: absolute; top: -4px; height: 20px; width: 2px;
            background: var(--primary-text-color);
          }
          .pvlim-section-title { font-weight: 600; margin-bottom: 8px; font-size: 14px; }
          .pvlim-anomaly { padding: 10px; border-radius: 8px; background: #fde9e7; color: #b94c47; margin-top: 12px; font-size: 13px; }
        </style>

        <div class="pvlim-row pvlim-tiles"></div>

        <div class="pvlim-section-title">Mode</div>
        <div class="pvlim-modes"></div>

        <div class="pvlim-section-title">Inverter limit</div>
        <div class="pvlim-gauge-wrap">
          <div class="pvlim-gauge-bar">
            <div class="pvlim-gauge-fill" style="width: 100%;"></div>
            <div class="pvlim-gauge-target" style="left: 100%;"></div>
          </div>
          <div class="pvlim-gauge-label" style="min-width: 50px; text-align: right; font-weight: 600;">100%</div>
        </div>

        <div class="pvlim-anomaly" style="display: none;"></div>
      </ha-card>
    `;
    this._update();
    this._attachModeHandlers();
  }

  _attachModeHandlers() {
    this.querySelector(".pvlim-modes").addEventListener("click", (e) => {
      const btn = e.target.closest(".pvlim-mode-btn");
      if (!btn) return;
      const mode = btn.dataset.mode;
      this._hass.callService("select", "select_option", {
        entity_id: `select.${this._entryPrefix}_mode`,
        option: mode,
      });
    });
  }

  _update() {
    if (!this._hass) return;

    const status = this._val("sensor", "status", "starting");
    const chip = STATUS_CHIPS[status] || { label: status, color: "#666" };

    const tiles = [
      { label: "PV", value: this._val("sensor", "load") !== "—"
        ? `${Math.round(parseFloat(this._hass.states[`sensor.${this._entryPrefix}_load`]?.state || 0) + parseFloat(this._hass.states[`sensor.${this._entryPrefix}_target_w`]?.state || 0) - parseFloat(this._hass.states[`sensor.${this._entryPrefix}_load`]?.state || 0))}` : "—",
        unit: "W", custom: this._val("sensor", "target_w") },
      { label: "Load", value: this._val("sensor", "load"), unit: "W" },
      { label: "Target %", value: this._val("sensor", "target_pct"), unit: "%" },
      { label: "Curtail", value: this._val("sensor", "curtailment_w"), unit: "W" },
      { label: "Status", html: `<span class="pvlim-status-chip" style="background:${chip.color}">${chip.label}</span>` },
    ];

    const tilesHtml = tiles
      .map((t) => {
        const inner = t.html
          ? t.html
          : `<div class="value">${t.value}<span class="unit">${t.unit || ""}</span></div>`;
        return `<div class="pvlim-tile"><div class="label">${t.label}</div>${inner}</div>`;
      })
      .join("");
    this.querySelector(".pvlim-tiles").innerHTML = tilesHtml;

    // Mode buttons
    const currentMode = this._val("select", "mode", "normal");
    const allModes = ["normal", "vacation", "negative_price", "wide", "manual", "off"];
    const modeLabels = {
      normal: "Normal", vacation: "Vacation", negative_price: "Neg. price",
      wide: "Wide", manual: "Manual", off: "Off",
    };
    this.querySelector(".pvlim-modes").innerHTML = allModes
      .map(
        (m) => `<button class="pvlim-mode-btn ${m === currentMode ? "active" : ""}" data-mode="${m}">${modeLabels[m]}</button>`
      )
      .join("");

    // Gauge
    const currentPct = parseFloat(this._val("sensor", "current_pct", 100));
    const targetPct = parseFloat(this._val("sensor", "target_pct", 100));
    const fill = this.querySelector(".pvlim-gauge-fill");
    const target = this.querySelector(".pvlim-gauge-target");
    const label = this.querySelector(".pvlim-gauge-label");
    if (fill) fill.style.width = `${Math.max(0, Math.min(100, currentPct))}%`;
    if (target) target.style.left = `${Math.max(0, Math.min(100, targetPct))}%`;
    if (label) label.textContent = `${currentPct.toFixed(1)}%`;

    // Anomaly banner
    const anomaly = this._hass.states[`binary_sensor.${this._entryPrefix}_anomaly`];
    const voltage = this._hass.states[`binary_sensor.${this._entryPrefix}_voltage_warning`];
    const banner = this.querySelector(".pvlim-anomaly");
    if (anomaly?.state === "on" || voltage?.state === "on") {
      banner.style.display = "block";
      const msgs = [];
      if (anomaly?.state === "on") msgs.push("Anomaly: limiter is not constraining export.");
      if (voltage?.state === "on") msgs.push("Voltage warning: grid voltage above threshold.");
      banner.textContent = msgs.join(" ");
    } else {
      banner.style.display = "none";
    }
  }

  static getStubConfig() {
    return { entry_prefix: "solaredge_pv_export_limiter" };
  }
}

customElements.define("pv-limiter-card", PVLimiterCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "pv-limiter-card",
  name: "Solaredge PV Export Limiter",
  description: "Live status, mode selector, and gauge for Solaredge PV Export Limiter.",
});

console.info(
  "%c SOLAREDGE-PV-LIMITER-CARD %c v0.1.0 ",
  "color: white; background: #03a9f4; font-weight: 700;",
  "color: #03a9f4; background: white; font-weight: 700;"
);
