const $ = (selector) => document.querySelector(selector);

let monitorsCache = [];
let incidentsCache = [];
let refreshInProgress = false;
let chartRequestVersion = 0;
let chartResizeObserver = null;
let lastChartResults = [];

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}

function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

function formatMilliseconds(value) {
    if (value === null || value === undefined || value === "") return "—";
    const number = Number(value);
    return Number.isFinite(number)
        ? `${number.toLocaleString(undefined, { maximumFractionDigits: 2 })} ms`
        : "—";
}

function showMessage(message, type = "success") {
    const element = $("#message");
    element.textContent = message;
    element.className = `message visible ${type}`;
}

function clearMessage() {
    $("#message").textContent = "";
    $("#message").className = "message";
}

async function apiRequest(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...options.headers
        }
    });

    if (!response.ok) {
        const details = await response.text();
        throw new Error(`Request failed (${response.status}): ${details.slice(0, 250)}`);
    }

    if (response.status === 204) return null;
    return response.json();
}

function statusBadge(status) {
    const normalized = String(status || "unknown").toLowerCase();
    const allowed = ["up", "down", "timeout", "open", "resolved", "inactive", "unknown"];
    const safeStatus = allowed.includes(normalized) ? normalized : "unknown";
    return `<span class="badge badge-${safeStatus}">${escapeHTML(safeStatus)}</span>`;
}

function getMonitorStatus(monitor) {
    if (monitor.is_active === false) return "inactive";
    const status = String(monitor.latest_check?.status || "unknown").toLowerCase();
    return ["up", "down", "timeout"].includes(status) ? status : "unknown";
}

async function loadChecks(monitorId, limit = 1) {
    const result = await apiRequest(
        `/api/v1/monitors/${encodeURIComponent(monitorId)}/checks?limit=${encodeURIComponent(limit)}`
    );
    return Array.isArray(result) ? result : [];
}

function renderMonitorOptions() {
    const select = $("#chart-monitor-select");
    const previousValue = select.value;
    select.replaceChildren(new Option("Select a monitor", ""));

    monitorsCache.forEach((monitor) => {
        select.add(new Option(`${monitor.name} (ID: ${monitor.id})`, String(monitor.id)));
    });

    if (monitorsCache.some((monitor) => String(monitor.id) === previousValue)) {
        select.value = previousValue;
    } else if (monitorsCache.length) {
        select.value = String(monitorsCache[0].id);
    }
}

function renderStatistics() {
    $("#total-monitors").textContent = monitorsCache.length;
    $("#up-monitors").textContent = monitorsCache.filter((monitor) => getMonitorStatus(monitor) === "up").length;
    $("#down-monitors").textContent = monitorsCache.filter((monitor) => ["down", "timeout"].includes(getMonitorStatus(monitor))).length;

    const openCount = incidentsCache.filter(
        (incident) => String(incident.status || "").toLowerCase() === "open"
    ).length;

    $("#open-incidents").textContent = openCount;
    $("#sidebar-incident-count").textContent = openCount;
}

function renderMonitors() {
    const tbody = $("#monitors-table");
    const search = $("#monitor-search").value.trim().toLowerCase();
    const selectedStatus = $("#monitor-status-filter").value;

    const filtered = monitorsCache.filter((monitor) => {
        const status = getMonitorStatus(monitor);
        const matchesSearch = [monitor.name, monitor.url, monitor.id].some(
            (value) => String(value ?? "").toLowerCase().includes(search)
        );
        return matchesSearch && (selectedStatus === "all" || status === selectedStatus);
    });

    $("#monitor-count").textContent = `${filtered.length} of ${monitorsCache.length} monitor${monitorsCache.length === 1 ? "" : "s"}`;
    $("#monitor-table-footer").textContent = `Showing ${filtered.length} of ${monitorsCache.length} monitors`;

    if (!filtered.length) {
        const message = monitorsCache.length
            ? "No monitors match your search or status filter."
            : "No monitors found. Create one using the API documentation.";
        tbody.innerHTML = `<tr><td colspan="5" class="empty">${message}</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map((monitor) => {
        const status = getMonitorStatus(monitor);
        const check = monitor.latest_check;
        const action = monitor.is_active === false
            ? '<span class="subtext">Inactive</span>'
            : `<button class="check-button" data-check-id="${escapeHTML(monitor.id)}" type="button">Check now</button>`;

        return `
            <tr>
                <td>
                    <span class="monitor-name">${escapeHTML(monitor.name)}</span>
                    <span class="endpoint-url">${escapeHTML(monitor.url)}</span>
                    <span class="subtext">Monitor ID: ${escapeHTML(monitor.id)}</span>
                </td>
                <td>${statusBadge(status)}</td>
                <td>${escapeHTML(formatMilliseconds(check?.response_time_ms))}</td>
                <td>${escapeHTML(check?.checked_at ? formatDate(check.checked_at) : "Not checked yet")}</td>
                <td>${action}</td>
            </tr>
        `;
    }).join("");
}

function renderIncidents() {
    const filter = $("#incident-filter").value;
    const filtered = incidentsCache.filter((incident) => {
        const status = String(incident.status || "").toLowerCase();
        return filter === "all" || status === filter;
    });
    const tbody = $("#incidents-table");

    if (!filtered.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty">No incidents match this filter.</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map((incident) => `
        <tr>
            <td><span class="monitor-name">#${escapeHTML(incident.id)}</span></td>
            <td>
                <span class="monitor-name">${escapeHTML(incident.monitor_name || `Monitor ${incident.monitor_id}`)}</span>
                <span class="subtext">Monitor ID: ${escapeHTML(incident.monitor_id)}</span>
            </td>
            <td>${statusBadge(incident.status)}</td>
            <td>${escapeHTML(incident.description || "—")}</td>
            <td>${escapeHTML(formatDate(incident.started_at))}</td>
            <td>${escapeHTML(formatDate(incident.resolved_at))}</td>
        </tr>
    `).join("");
}

function clearChart(message) {
    const canvas = $("#response-chart");
    const context = canvas.getContext("2d");
    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;

    canvas.width = Math.max(1, Math.round(rect.width * ratio));
    canvas.height = Math.max(1, Math.round(rect.height * ratio));
    context.clearRect(0, 0, canvas.width, canvas.height);

    $("#chart-empty").textContent = message;
    $("#chart-empty").hidden = false;
    $("#chart-latest-value").textContent = "—";
    $("#chart-average-value").textContent = "—";
    $("#chart-check-count").textContent = "No data";
}

function drawResponseChart(results) {
    const canvas = $("#response-chart");
    const context = canvas.getContext("2d");
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(rect.width, 280);
    const height = Math.max(rect.height, 180);
    const ratio = window.devicePixelRatio || 1;

    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);

    const valid = results.filter((item) =>
        item.response_time_ms !== null &&
        item.response_time_ms !== undefined &&
        Number.isFinite(Number(item.response_time_ms)) &&
        Number(item.response_time_ms) >= 0
    ).sort((a, b) => new Date(a.checked_at).getTime() - new Date(b.checked_at).getTime());

    $("#chart-check-count").textContent = `${results.length} recorded check${results.length === 1 ? "" : "s"}`;

    if (!valid.length) {
        $("#chart-empty").textContent = results.length
            ? "No checks have a recorded response time."
            : "No check history is available for this monitor.";
        $("#chart-empty").hidden = false;
        $("#chart-latest-value").textContent = "—";
        $("#chart-average-value").textContent = "—";
        return;
    }

    $("#chart-empty").hidden = true;
    const values = valid.map((item) => Number(item.response_time_ms));
    const latest = values[values.length - 1];
    const average = values.reduce((sum, value) => sum + value, 0) / values.length;
    $("#chart-latest-value").textContent = formatMilliseconds(latest);
    $("#chart-average-value").textContent = formatMilliseconds(average);

    const padding = { top: 15, right: 17, bottom: 33, left: 49 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    if (plotWidth <= 0 || plotHeight <= 0) return;

    const max = Math.max(...values, 1) * 1.15;
    const x = (i) => padding.left + (values.length === 1 ? plotWidth / 2 : i * plotWidth / (values.length - 1));
    const y = (value) => padding.top + plotHeight - (value / max) * plotHeight;

    context.font = "10px DM Sans, Segoe UI, sans-serif";
    context.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const value = max * i / 4;
        const py = y(value);
        context.strokeStyle = "#303038";
        context.beginPath();
        context.moveTo(padding.left, py);
        context.lineTo(width - padding.right, py);
        context.stroke();
        context.fillStyle = "#858391";
        context.textAlign = "right";
        context.textBaseline = "middle";
        context.fillText(`${value.toFixed(value >= 100 ? 0 : 1)} ms`, padding.left - 8, py);
    }

    context.beginPath();
    valid.forEach((item, i) => i === 0 ? context.moveTo(x(i), y(values[i])) : context.lineTo(x(i), y(values[i])));
    if (valid.length > 1) {
        context.lineTo(x(valid.length - 1), padding.top + plotHeight);
        context.lineTo(x(0), padding.top + plotHeight);
        context.closePath();
        const gradient = context.createLinearGradient(0, padding.top, 0, padding.top + plotHeight);
        gradient.addColorStop(0, "rgba(167, 139, 250, .20)");
        gradient.addColorStop(1, "rgba(167, 139, 250, .005)");
        context.fillStyle = gradient;
        context.fill();
    }

    context.beginPath();
    valid.forEach((item, i) => i === 0 ? context.moveTo(x(i), y(values[i])) : context.lineTo(x(i), y(values[i])));
    context.strokeStyle = "#b19aff";
    context.lineWidth = 2.3;
    context.lineJoin = "round";
    context.lineCap = "round";
    context.stroke();

    valid.forEach((item, i) => {
        context.beginPath();
        context.arc(x(i), y(values[i]), 2.8, 0, Math.PI * 2);
        context.fillStyle = "#1a1a1f";
        context.fill();
        context.strokeStyle = "#c2afff";
        context.lineWidth = 1.7;
        context.stroke();
    });

    const indexes = [...new Set([0, Math.floor((valid.length - 1) / 2), valid.length - 1])];
    context.fillStyle = "#858391";
    context.textBaseline = "alphabetic";
    indexes.forEach((index) => {
        const date = new Date(valid[index].checked_at);
        const label = Number.isNaN(date.getTime()) ? `Check ${index + 1}` : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        context.textAlign = index === 0 ? "left" : index === valid.length - 1 ? "right" : "center";
        context.fillText(label, x(index), height - 8);
    });
}

async function loadSelectedMonitorChart() {
    const version = ++chartRequestVersion;
    const monitorId = $("#chart-monitor-select").value;

    if (!monitorId) {
        lastChartResults = [];
        clearChart("Add or select a monitor to view response-time history.");
        return;
    }

    $("#chart-empty").textContent = "Loading response-time history…";
    $("#chart-empty").hidden = false;

    try {
        const results = await loadChecks(monitorId, 50);
        if (version !== chartRequestVersion) return;
        lastChartResults = results;
        drawResponseChart(results);
    } catch (error) {
        if (version !== chartRequestVersion) return;
        console.error("Could not load response-time history:", error);
        clearChart("Could not load chart data. Verify the check-history endpoint and try refreshing.");
    }
}

async function refreshDashboard() {
    if (refreshInProgress) return;
    refreshInProgress = true;
    $("#refresh-button").disabled = true;
    clearMessage();

    try {
        const [monitors, incidents] = await Promise.all([
            apiRequest("/api/v1/monitors"),
            apiRequest("/api/v1/incidents?limit=100")
        ]);

        if (!Array.isArray(monitors) || !Array.isArray(incidents)) {
            throw new Error("The API returned an unexpected data format.");
        }

        const enriched = await Promise.all(monitors.map(async (monitor) => {
            try {
                const checks = await loadChecks(monitor.id, 1);
                return { ...monitor, latest_check: checks[0] ?? null };
            } catch (error) {
                console.error(`Could not load checks for monitor ${monitor.id}`, error);
                return { ...monitor, latest_check: null };
            }
        }));

        monitorsCache = enriched;
        incidentsCache = incidents;
        renderStatistics();
        renderMonitorOptions();
        renderMonitors();
        renderIncidents();
        $("#last-updated").textContent = new Date().toLocaleTimeString();

        await loadSelectedMonitorChart();
    } catch (error) {
        console.error("Dashboard refresh failed:", error);
        showMessage(`Could not load dashboard data. Check that FastAPI is running. ${error.message}`, "error");
    } finally {
        refreshInProgress = false;
        $("#refresh-button").disabled = false;
    }
}

document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-check-id]");
    if (!button) return;

    const monitorId = button.dataset.checkId;
    button.disabled = true;
    button.textContent = "Checking…";

    try {
        await apiRequest(`/api/v1/monitors/${encodeURIComponent(monitorId)}/check`, { method: "POST" });
        showMessage(`Manual check completed for monitor ${monitorId}.`, "success");
        await refreshDashboard();
    } catch (error) {
        showMessage(`Manual check failed: ${error.message}`, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Check now";
    }
});

$("#refresh-button").addEventListener("click", refreshDashboard);
$("#incident-filter").addEventListener("change", renderIncidents);
$("#monitor-search").addEventListener("input", renderMonitors);
$("#monitor-status-filter").addEventListener("change", renderMonitors);

$("#chart-monitor-select").addEventListener("change", loadSelectedMonitorChart);

document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", () => {
        document.querySelectorAll(".nav-link").forEach((item) => item.classList.remove("active"));
        link.classList.add("active");
    });
});

if ("ResizeObserver" in window) {
    chartResizeObserver = new ResizeObserver(() => {
        if (lastChartResults.length) drawResponseChart(lastChartResults);
    });
    chartResizeObserver.observe($("#response-chart"));
} else {
    window.addEventListener("resize", () => {
        if (lastChartResults.length) drawResponseChart(lastChartResults);
    });
}

refreshDashboard();
setInterval(refreshDashboard, 30000);
