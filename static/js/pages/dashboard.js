import { $, escapeHTML, setText } from "../utils.js";
import { loadLogs, logRowHTML } from "../visitor-logs.js";
import { loadInsideVisitors } from "../visitor-entry-exit.js";
import { loadApprovals } from "../visitor-approval.js";
import { setButtonLoading } from "../loading.js";
import { emptyStateHTML } from "../empty-state.js";

const LOAD_ERROR = {
    icon: "⚠️",
    title: "Could not load data",
    message: "The server did not respond. This panel will retry automatically.",
    variant: "error"
};

function emptyRow(state) {
    return `<tr><td colspan="4">${state}</td></tr>`;
}

function renderRecentActivity(logs) {
    const tbody = $("recentActivityBody");
    if (!tbody) return;

    if (logs === null) {
        tbody.innerHTML = emptyRow(emptyStateHTML(LOAD_ERROR));
        return;
    }

    const recent = logs.slice(0, 8);

    if (!recent.length) {
        tbody.innerHTML = emptyRow(emptyStateHTML({
            icon: "📖",
            title: "No visitor activity yet",
            message: "Recognition events will appear here once the camera identifies visitors."
        }));
        return;
    }

    tbody.innerHTML = recent.map(logRowHTML).join("");
}

function renderPendingSummary(approvals) {
    const list = $("pendingSummaryList");
    if (!list) return;

    if (approvals === null) {
        list.innerHTML = emptyStateHTML(LOAD_ERROR);
        return;
    }

    setText("pendingVisitors", approvals.length);
    setText("pendingSummaryBadge", approvals.length + " Pending");

    if (!approvals.length) {
        list.innerHTML = emptyStateHTML({
            icon: "🕐",
            title: "No pending approvals",
            message: "New visitor requests will appear here for host review."
        });
        return;
    }

    list.innerHTML = approvals.slice(0, 5).map(visitor => {
        const name = visitor.Name || visitor.name || "Visitor";
        const host = visitor.Host || visitor.host || "Not provided";
        const time = visitor["Registration Time"] ||
            visitor.registration_time || "";

        return `
            <div class="list-item">
                <h4>${escapeHTML(name)}</h4>
                <p>Host: ${escapeHTML(host)}<br>
                   Registered: ${escapeHTML(time || "Not available")}</p>
            </div>
        `;
    }).join("");
}

function renderInsideSummary(visitors) {
    const list = $("insideSummaryList");
    if (!list) return;

    if (visitors === null) {
        list.innerHTML = emptyStateHTML(LOAD_ERROR);
        return;
    }

    setText("insideSummaryBadge", visitors.length + " Visitors");

    if (!visitors.length) {
        list.innerHTML = emptyStateHTML({
            icon: "🏢",
            title: "No visitors currently inside",
            message: "When an approved visitor is marked as entered, they will appear here."
        });
        return;
    }

    list.innerHTML = visitors.slice(0, 5).map(visitor => {
        const name = visitor.Name || visitor.name ||
            visitor["Visitor Name"] || "Unknown";
        const time = visitor["Entry Time"] ||
            visitor.entry_time || visitor.time || "";

        return `
            <div class="list-item">
                <h4>${escapeHTML(name)}</h4>
                <p>Entry time: ${escapeHTML(time || "Not available")}</p>
            </div>
        `;
    }).join("");
}

async function refreshOverview() {
    const logsPromise = $("recentActivityBody")
        ? loadLogs()
        : Promise.resolve([]);
    const approvalsPromise = $("pendingSummaryList")
        ? loadApprovals()
        : Promise.resolve([]);
    const visitorsPromise = $("insideSummaryList")
        ? loadInsideVisitors()
        : Promise.resolve([]);

    const [logs, approvals, visitors] = await Promise.all([
        logsPromise,
        approvalsPromise,
        visitorsPromise
    ]);

    renderRecentActivity(logs);
    renderPendingSummary(approvals);
    renderInsideSummary(visitors);
}

const refreshButton = $("refreshButton");
if (refreshButton) {
    refreshButton.addEventListener("click", async () => {
        setButtonLoading(refreshButton, true, "Refreshing...");
        try {
            await refreshOverview();
        } finally {
            setButtonLoading(refreshButton, false);
        }
    });
}

refreshOverview();

// Keep the overview current without starting face recognition.
setInterval(refreshOverview, 10000);
