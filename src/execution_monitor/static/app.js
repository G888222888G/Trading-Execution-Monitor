"use strict";

const phaseOrder = [
  "checking_order",
  "sending_order",
  "waiting_for_fill",
  "order_partly_filled",
  "order_fully_filled",
  "reconciled",
];

const phaseLabels = {
  no_active_order: "Ready for next order",
  checking_order: "Checking request",
  sending_order: "Sending to venue",
  waiting_for_fill: "Waiting for fill",
  order_partly_filled: "Order partly filled",
  order_fully_filled: "Order fully filled",
  reconciled: "Records reconciled",
  order_cancelled: "Order cancelled",
  order_failed: "Order failed",
};

const statusCopy = {
  safe: {
    title: "System operating safely",
    summary: "Execution protected • Safety checks passed • Monitoring active",
  },
  warning: {
    title: "Records need attention",
    summary: "Execution is contained • Local and venue records differ",
  },
  blocked: {
    title: "Execution blocked safely",
    summary: "Protection is active • No new execution can continue",
  },
};

const safetyElements = Array.from(document.querySelectorAll("[data-check]"));
const recordElements = Array.from(document.querySelectorAll("[data-record]"));
const phaseElements = Array.from(document.querySelectorAll("[data-phase]"));

function formatMode(mode) {
  return String(mode || "connecting").replaceAll("_", " ").toUpperCase();
}

function formatEventTime(value) {
  if (!value) return "Time unavailable";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Time unavailable";
  return parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function setHealthRow(element, passed, passCopy, failCopy) {
  const success = Boolean(passed);
  element.classList.toggle("pass", success);
  element.classList.toggle("fail", !success);
  element.querySelector("strong").textContent = success ? passCopy : failCopy;
  const label = element.querySelector(".health-label").textContent.trim();
  element.setAttribute("aria-label", `${label}: ${success ? passCopy : failCopy}`);
}

function renderTimeline(payload) {
  const phase = payload.execution_phase || payload.order_stage;
  const activeIndex = phaseOrder.indexOf(phase);
  const terminal = phase === "order_cancelled" || phase === "order_failed";

  phaseElements.forEach((element, index) => {
    element.classList.remove("is-complete", "is-active", "is-pending");
    let state = "is-pending";
    if (!terminal && activeIndex >= 0) {
      if (index < activeIndex) state = "is-complete";
      if (index === activeIndex) state = "is-active";
    }
    element.classList.add(state);
    element.setAttribute("aria-current", state === "is-active" ? "step" : "false");
    element.querySelector(".step-marker").textContent = state === "is-complete" ? "✓" : String(index + 1);
  });

  document.getElementById("phase-value").textContent = phaseLabels[phase] || "Monitoring";
  const branch = document.getElementById("branch-message");
  branch.hidden = !terminal;
  branch.textContent = terminal ? phaseLabels[phase] : "";
  branch.className = `branch-message ${phase === "order_failed" ? "branch-failed" : "branch-cancelled"}`;
}

function render(payload) {
  const status = statusCopy[payload.overall_status] ? payload.overall_status : "blocked";
  const connectionHealthy = Boolean(payload.safety_checks.connection_healthy);
  document.body.dataset.status = status;
  document.getElementById("mode-value").textContent = formatMode(payload.mode);
  document.getElementById("connection-copy").textContent = connectionHealthy ? "CONNECTED" : "DISCONNECTED";
  document.getElementById("connection-value").classList.toggle("is-offline", !connectionHealthy);
  document.getElementById("status-title").textContent = statusCopy[status].title;
  document.getElementById("status-summary").textContent = statusCopy[status].summary;
  document.getElementById("status-detail").textContent = payload.status_reason;
  document.getElementById("last-checked").textContent = "Checked just now";
  document.getElementById("latest-event").textContent = payload.latest_event;
  document.getElementById("latest-event-time").textContent = formatEventTime(payload.latest_event_at);

  renderTimeline(payload);

  const safetyCopy = {
    duplicate_protection: ["PROTECTED", "UNAVAILABLE"],
    risk_limit_active: ["ACTIVE", "UNAVAILABLE"],
    connection_healthy: ["HEALTHY", "OFFLINE"],
    emergency_stop_ready: ["READY", "ENGAGED"],
  };
  safetyElements.forEach((element) => {
    const key = element.dataset.check;
    setHealthRow(element, payload.safety_checks[key], safetyCopy[key][0], safetyCopy[key][1]);
  });
  recordElements.forEach((element) => {
    setHealthRow(element, payload.reconciliation[element.dataset.record], "MATCHED", "MISMATCH");
  });
}

function renderOffline() {
  document.body.dataset.status = "blocked";
  document.getElementById("mode-value").textContent = "OFFLINE";
  document.getElementById("connection-copy").textContent = "DISCONNECTED";
  document.getElementById("connection-value").classList.add("is-offline");
  document.getElementById("status-title").textContent = "Monitor unavailable";
  document.getElementById("status-summary").textContent = "The dashboard cannot verify execution state";
  document.getElementById("status-detail").textContent = "Restart the local monitor server to reconnect.";
  document.getElementById("last-checked").textContent = "Connection lost";
  document.getElementById("phase-value").textContent = "Unavailable";
  document.getElementById("latest-event").textContent = "Waiting for the local Execution Monitor.";
  document.getElementById("latest-event-time").textContent = "No current event";
  phaseElements.forEach((element, index) => {
    element.className = "is-pending";
    element.setAttribute("aria-current", "false");
    element.querySelector(".step-marker").textContent = String(index + 1);
  });
  safetyElements.forEach((element) => setHealthRow(element, false, "READY", "UNAVAILABLE"));
  recordElements.forEach((element) => setHealthRow(element, false, "MATCHED", "UNKNOWN"));
}

async function refresh() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) throw new Error(`Status request failed: ${response.status}`);
    render(await response.json());
  } catch (error) {
    console.warn(error);
    renderOffline();
  }
}

refresh();
window.setInterval(refresh, 1000);
