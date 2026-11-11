import { $, escapeHTML, fetchJSON, setText } from "./utils.js";
import { setButtonLoading } from "./loading.js";
import { emptyStateHTML } from "./empty-state.js";
import { createPaginator } from "./pagination.js";

let allLogs = [];
let paginator = null;

function getPaginator() {
    if (!paginator) {
        paginator = createPaginator({
            controlsId: "logsPager",
            summaryId: "logsSummary",
            pageSize: 10,
            label: "events",
            onChange: () => renderLogs(allLogs)
        });
    }
    return paginator;
}

function resetAndRender() {
    getPaginator().reset();
    renderLogs(allLogs);
}

export function logRowHTML(log) {
    const status = String(log.Status ?? "");
    const recognized = status.toLowerCase() === "recognized";

    return `
        <tr>
            <td>${escapeHTML(log["Visitor Name"])}</td>
            <td>${escapeHTML(log.Date)}</td>
            <td>${escapeHTML(log.Time)}</td>
            <td>
                <span class="badge ${recognized ? "badge-green" : "badge-red"}">
                    ${escapeHTML(status || "Unknown")}
                </span>
            </td>
        </tr>
    `;
}

function emptyRow(state) {
    return `<tr><td colspan="4">${state}</td></tr>`;
}

function renderLogs(logs) {
    const search = $("logSearch");
    const query = search ? search.value.trim().toLowerCase() : "";

    const filtered = logs.filter(log =>
        Object.values(log).some(value =>
            String(value ?? "").toLowerCase().includes(query)
        )
    );

    const view = getPaginator().paginate(filtered);

    const tbody = $("logsTableBody");
    if (!tbody) return;

    if (!view.total) {
        // Distinguish "search matched nothing" from "no data at all".
        tbody.innerHTML = emptyRow(
            query
                ? emptyStateHTML({
                    icon: "🔍",
                    title: "No matching visitor logs",
                    message: "No logs match \"" + search.value.trim() + "\".",
                    action: { label: "Clear Search", id: "clearLogSearch" }
                })
                : emptyStateHTML({
                    icon: "📖",
                    title: "No visitor logs yet",
                    message: "Recognition events will be recorded here once the camera identifies visitors."
                })
        );
        return;
    }

    tbody.innerHTML = view.items.map(logRowHTML).join("");
}

export async function loadLogs() {
    try {
        const data = await fetchJSON("/api/visitor-logs");

        if (Array.isArray(data)) {
            allLogs = data;
        } else {
            allLogs = data.logs || [];
            if (data.total_visitors !== undefined) {
                setText("totalVisitors", data.total_visitors);
            }
            if (data.recognized !== undefined) {
                setText("recognizedVisitors", data.recognized);
            }
            if (data.unknown !== undefined) {
                setText("unknownVisitors", data.unknown);
            }
        }

        renderLogs(allLogs);
        return allLogs;
    } catch (error) {
        console.error("Could not load visitor logs:", error);

        // Keep showing the last known data if we have it; otherwise show
        // an explicit error state instead of a misleading "no logs" state.
        if (!allLogs.length) {
            const tbody = $("logsTableBody");
            if (tbody) {
                tbody.innerHTML = emptyRow(emptyStateHTML({
                    icon: "⚠️",
                    title: "Could not load visitor logs",
                    message: "The server did not respond. The table will retry automatically.",
                    variant: "error"
                }));
            }
            setText("logsSummary", "Could not load visitor logs.");
            return null;
        }

        return allLogs;
    }
}

export function initVisitorLogs() {
    const search = $("logSearch");
    const refreshButton = $("refreshLogsButton");

    if (search) {
        search.addEventListener("input", resetAndRender);
    }

    const tbody = $("logsTableBody");
    if (tbody) {
        tbody.addEventListener("click", event => {
            if (event.target.id === "clearLogSearch" && search) {
                search.value = "";
                resetAndRender();
                search.focus();
            }
        });
    }

    if (refreshButton) {
        refreshButton.addEventListener("click", async () => {
            setButtonLoading(refreshButton, true, "Refreshing...");
            try {
                await loadLogs();
            } finally {
                setButtonLoading(refreshButton, false);
            }
        });
    }
}
