import { $, escapeHTML, setText } from "../utils.js";
import { loadLogs, logRowHTML } from "../visitor-logs.js";
import { loadInsideVisitors } from "../visitor-entry-exit.js";
import { loadApprovals } from "../visitor-approval.js";
import { setButtonLoading } from "../loading.js";

function renderRecentActivity(logs) {
    const tbody = $("recentActivityBody");
    if (!tbody) return;

    const recent = logs.slice(0, 8);

    if (!recent.length) {
        tbody.innerHTML =
            '<tr><td colspan="4" class="empty-state">No visitor activity yet.</td></tr>';
        return;
    }

    tbody.innerHTML = recent.map(logRowHTML).join("");
}

function renderPendingSummary(approvals) {
    const list = $("pendingSummaryList");
    if (!list) return;

    setText("pendingVisitors", approvals.length);
    setText("pendingSummaryBadge", approvals.length + " Pending");

    if (!approvals.length) {
        list.innerHTML =
            '<div class="empty-state">No pending approvals.</div>';
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

    setText("insideSummaryBadge", visitors.length + " Visitors");

    if (!visitors.length) {
        list.innerHTML =
            '<div class="empty-state">No visitors currently inside.</div>';
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
    const [logs, approvals, visitors] = await Promise.all([
        loadLogs(),
        loadApprovals(),
        loadInsideVisitors()
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
