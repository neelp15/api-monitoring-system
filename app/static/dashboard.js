
const $ = (selector) => document.querySelector(selector);

let monitorsCache = [];
let incidentsCache = [];
let refreshInProgress = false;
let chartRequestVersion = 0;
let chartResizeObserver = null;

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
    return Number.isNaN(date.getTime())
        ? "—"
        : date.toLocaleString();
}

function formatMilliseconds(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }

    const number = Number(value);

    return Number.isFinite(number)
        ? `${number.toLocaleString(undefined, {
            maximumFractionDigits: 2
        })} ms`
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
        throw new Error(
            `Request failed (${response.status}): ${details.slice(0, 250)}`
        );
    }

    if (response.status === 204) return null;

    return response.json();
}

function statusBadge(status) {
    const normalized = String(status || "unknown").toLowerCase();
    const allowed = [
        "up",
        "down",
        "timeout",
        "open",
        "resolved",
        "inactive",
        "unknown"
    ];

    const safeStatus = allowed.includes(normalized)
        ? normalized
        : "unknown";

    return `
        <span class="badge badge-${safeStatus}">
            ${escapeHTML(safeStatus)}
        </span>
    `;
}

function getMonitorStatus(monitor) {
    if (monitor.is_active === false) return "inactive";

    const status = String(
        monitor.latest_check?.status || "unknown"
    ).toLowerCase();

    return ["up", "down", "timeout"].includes(status)
        ? status
        : "unknown";
}

async function loadChecks(monitorId, limit = 1) {
    return apiRequest(
        `/api/v1/monitors/${encodeURIComponent(monitorId)}/checks?limit=${limit}`
    );
}

function renderMonitorOptions(monitors) {
    const select = $("#chart-monitor-select");
    const previousValue = select.value;

    select.innerHTML = '<option value="">Select a monitor</option>';

    monitors.forEach((monitor) => {
        const option = document.createElement("option");
        option.value = String(monitor.id);
        option.textContent = `${monitor.name} (ID: ${monitor.id})`;
        select.appendChild(option);
    });

    if (monitors.some(
        (monitor) => String(monitor.id) === previousValue
    )) {
        select.value = previousValue;
    } else if (monitors.length) {
        select.value = String(monitors[0].id);
    }
}

function renderMonitors() {
    const tbody = $("#monitors-table");
    const search = $("#monitor-search").value.trim().toLowerCase();
    const selectedStatus = $("#monitor-status-filter").value;

    const filtered = monitorsCache.filter((monitor) => {
        const status = getMonitorStatus(monitor);

        const matchesSearch = [
            monitor.name,
            monitor.url,
            monitor.id
        ].some((value) =>
            String(value ?? "").toLowerCase().includes(search)
        );

        const matchesStatus =
            selectedStatus === "all" || status === selectedStatus;

        return matchesSearch && matchesStatus;
    });

    $("#monitor-count").textContent =
        `${filtered.length} of ${monitorsCache.length} monitor${monitorsCache.length === 1 ? "" : "s"}`;

    $("#monitor-table-footer").textContent =
        `Showing ${filtered.length} of ${monitorsCache.length} monitors`;

    if (!filtered.length) {
        const message = monitorsCache.length
            ? "No monitors match your search or status filter."
            : "No monitors found. Create a monitor using the API documentation.";

        tbody.innerHTML = `
            <tr><td colspan="6" class="empty">${message}</td></tr>
        `;
        return;
    }

    tbody.innerHTML = filtered.map((monitor) => {
        const check = monitor.latest_check;
        const status = getMonitorStatus(monitor);
        const latency = formatMilliseconds(check?.response_time_ms);
        const lastChecked = check?.checked_at
            ? formatDate(check.checked_at)
            : "Not checked yet";

        const action = monitor.is_active === false
            ? '<span class="subtext">Inactive</span>'
            : `
                <button
                    class="check-button"
                    data-check-id="${escapeHTML(monitor.id)}"
                    type="button">
                    Check now
                </button>
            `;

        return `
            <tr>
                <td>
                    <span class="monitor-name">${escapeHTML(monitor.name)}</span>
                    <span class="subtext">ID: ${escapeHTML(monitor.id)}</span>
                </td>
                <td class="url-cell">${escapeHTML(monitor.url)}</td>
                <td>${statusBadge(status)}</td>
                <td>${escapeHTML(latency)}</td>
                <td>${escapeHTML(lastChecked)}</td>
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
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty">
                    No incidents match this filter.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = filtered.map((incident) => `
        <tr>
            <td>
                <span class="monitor-name">#${escapeHTML(incident.id)}</span>
            </td>
            <td>
                <span class="monitor-name">
                    ${escapeHTML(
                        incident.monitor_name ||
                        `Monitor ${incident.monitor_id}`
                    )}
                </span>
                <span class="subtext">
                    ID: ${escapeHTML(incident.monitor_id)}
                </span>
            </td>
            <td>${statusBadge(incident.status)}</td>
            <td>${escapeHTML(incident.description || "—")}</td>
            <td>${escapeHTML(formatDate(incident.started_at))}</td>
            <td>${escapeHTML(formatDate(incident.resolved_at))}</td>
        </tr>
    `).join("");
}

function renderStatistics() {
    const upCount = monitorsCache.filter(
        (monitor) => getMonitorStatus(monitor) === "up"
    ).length;

    const downCount = monitorsCache.filter(
        (monitor) => ["down", "timeout"].includes(getMonitorStatus(monitor))
    ).length;

    const openCount = incidentsCache.filter(
        (incident) => String(incident.status).toLowerCase() === "open"
    ).length;

    $("#total-monitors").textContent = monitorsCache.length;
    $("#up-monitors").textContent = upCount;
    $("#down-monitors").textContent = downCount;
    $("#open-incidents").textContent = openCount;
    $("#sidebar-incident-count").textContent = openCount;
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

        const monitorsWithChecks = await Promise.all(
            monitors.map(async (monitor) => {
                try {
                    const results = await loadChecks(monitor.id, 1);

                    return {
                        ...monitor,
                        latest_check: Array.isArray(results)
                            ? results[0] ?? null
                            : null
                    };
                } catch (error) {
                    console.error(
                        `Could not load checks for monitor ${monitor.id}`,
                        error
                    );

                    return {
                        ...monitor,
                        latest_check: null,
                        check_load_failed: true
                    };
                }
            })
        );

        monitorsCache = monitorsWithChecks;
        incidentsCache = incidents;

        renderStatistics();
        renderMonitorOptions(monitorsCache);
        renderMonitors();
        renderIncidents();

        $("#last-updated").textContent =
            `Updated ${new Date().toLocaleTimeString()}`;

        await loadSelectedMonitorChart();
    } catch (error) {
        console.error("Dashboard refresh failed:", error);

        showMessage(
            `Could not load dashboard data. Check that the FastAPI server is running. ${error.message}`,
            "error"
        );
    } finally {
        refreshInProgress = false;
        $("#refresh-button").disabled = false;
    }
}

function clearChart(message) {
    const canvas = $("#response-chart");
    const context = canvas.getContext("2d");

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
    const pixelRatio = window.devicePixelRatio || 1;

    canvas.width = Math.round(width * pixelRatio);
    canvas.height = Math.round(height * pixelRatio);

    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    context.clearRect(0, 0, width, height);

    const validResults = results
        .filter((result) =>
            result.response_time_ms !== null &&
            result.response_time_ms !== undefined &&
            Number.isFinite(Number(result.response_time_ms)) &&
            Number(result.response_time_ms) >= 0
        )
        .sort((a, b) =>
            new Date(a.checked_at).getTime() -
            new Date(b.checked_at).getTime()
        );

    $("#chart-check-count").textContent =
        `${results.length} recorded check${results.length === 1 ? "" : "s"}`;

    if (!validResults.length) {
        $("#chart-empty").textContent =
            results.length
                ? "No checks have a recorded response time."
                : "No check history is available for this monitor.";

        $("#chart-empty").hidden = false;
        $("#chart-latest-value").textContent = "—";
        $("#chart-average-value").textContent = "—";
        return;
    }

    $("#chart-empty").hidden = true;

    const values = validResults.map(
        (result) => Number(result.response_time_ms)
    );

    const latest = values[values.length - 1];
    const average = values.reduce((sum, value) => sum + value, 0)
        / values.length;

    $("#chart-latest-value").textContent = formatMilliseconds(latest);
    $("#chart-average-value").textContent = formatMilliseconds(average);

    const padding = { top: 16, right: 18, bottom: 35, left: 50 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;

    if (plotWidth <= 0 || plotHeight <= 0) return;

    const maximum = Math.max(...values, 1);
    const yMaximum = maximum * 1.15;

    const x = (index) => padding.left +
        (validResults.length === 1
            ? plotWidth / 2
            : index * plotWidth / (validResults.length - 1));

    const y = (value) =>
        padding.top + plotHeight - (value / yMaximum) * plotHeight;

    context.font = "10px Segoe UI, Arial, sans-serif";
    context.textBaseline = "middle";
    context.lineWidth = 1;

    for (let i = 0; i <= 4; i++) {
        const value = yMaximum * i / 4;
        const yPosition = y(value);

        context.strokeStyle = "#edf0f6";
        context.beginPath();
        context.moveTo(padding.left, yPosition);
        context.lineTo(width - padding.right, yPosition);
        context.stroke();

        context.fillStyle = "#8792a6";
        context.textAlign = "right";
        context.fillText(
            `${value.toFixed(value >= 100 ? 0 : 1)} ms`,
            padding.left - 9,
            yPosition
        );
    }

    const gradient = context.createLinearGradient(
        0,
        padding.top,
        0,
        padding.top + plotHeight
    );

    gradient.addColorStop(0, "rgba(82, 111, 240, 0.22)");
    gradient.addColorStop(1, "rgba(82, 111, 240, 0.01)");

    context.beginPath();

    validResults.forEach((result, index) => {
        if (index === 0) {
            context.moveTo(x(index), y(values[index]));
        } else {
            context.lineTo(x(index), y(values[index]));
        }
    });

    if (validResults.length > 1) {
        context.lineTo(x(validResults.length - 1), padding.top + plotHeight);
        context.lineTo(x(0), padding.top + plotHeight);
        context.closePath();
        context.fillStyle = gradient;
        context.fill();
    }

    context.beginPath();

    validResults.forEach((result, index) => {
        if (index === 0) {
            context.moveTo(x(index), y(values[index]));
        } else {
            context.lineTo(x(index), y(values[index]));
        }
    });

    context.strokeStyle = "#526ff0";
    context.lineWidth = 2.5;
    context.lineJoin = "round";
    context.lineCap = "round";
    context.stroke();

    validResults.forEach((result, index) => {
        context.beginPath();
        context.arc(x(index), y(values[index]), 3, 0, Math.PI * 2);
        context.fillStyle = "#fff";
        context.fill();
        context.strokeStyle = "#526ff0";
        context.lineWidth = 2;
        context.stroke();
    });

    const labelIndexes = [...new Set([
        0,
        Math.floor((validResults.length - 1) / 2),
        validResults.length - 1
    ])];

    context.fillStyle = "#8792a6";
    context.textBaseline = "alphabetic";

    labelIndexes.forEach((index) => {
        const date = new Date(validResults[index].checked_at);

        const label = Number.isNaN(date.getTime())
            ? `Check ${index + 1}`
            : date.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit"
            });

        context.textAlign = index === 0
            ? "left"
            : index === validResults.length - 1
                ? "right"
                : "center";

        context.fillText(
            label,
            x(index),
            height - 9
        );
    });
}

async function loadSelectedMonitorChart() {
    const version = ++chartRequestVersion;
    const monitorId = $("#chart-monitor-select").value;

    if (!monitorId) {
        clearChart("Add a monitor to start viewing response-time history.");
        return;
    }

    $("#chart-empty").textContent = "Loading response-time history...";
    $("#chart-empty").hidden = false;

    try {
        const results = await loadChecks(monitorId, 50);

        if (version !== chartRequestVersion) return;

        if (!Array.isArray(results)) {
            throw new Error("Unexpected check-history response.");
        }

        drawResponseChart(results);
    } catch (error) {
        if (version !== chartRequestVersion) return;

        console.error("Could not load response-time history:", error);
        clearChart("Could not load chart data. Try refreshing the dashboard.");
    }
}

document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-check-id]");

    if (!button) return;

    const monitorId = button.dataset.checkId;
    button.disabled = true;
    button.textContent = "Checking...";

    try {
        await apiRequest(
            `/api/v1/monitors/${encodeURIComponent(monitorId)}/check`,
            { method: "POST" }
        );

        showMessage(
            `Manual check completed for monitor ${monitorId}.`,
            "success"
        );

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

$("#chart-monitor-select").addEventListener(
    "change",
    loadSelectedMonitorChart
);

document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", () => {
        document.querySelectorAll(".nav-link").forEach((item) => {
            item.classList.remove("active");
        });

        link.classList.add("active");
    });
});

if ("ResizeObserver" in window) {
    chartResizeObserver = new ResizeObserver(() => {
        if ($("#chart-monitor-select").value) {
            loadSelectedMonitorChart();
        }
    });

    chartResizeObserver.observe($("#response-chart"));
} else {
    window.addEventListener("resize", () => {
        if ($("#chart-monitor-select").value) {
            loadSelectedMonitorChart();
        }
    });
}

refreshDashboard();

setInterval(refreshDashboard, 30000);
