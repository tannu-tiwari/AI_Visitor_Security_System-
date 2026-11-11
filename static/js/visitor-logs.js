import { $, escapeHTML, fetchJSON, setText } from "./utils.js";

let allLogs = [];

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

function renderLogs(logs) {
    const search = $("logSearch");
    const query = search ? search.value.trim().toLowerCase() : "";

    const filtered = logs.filter(log =>
        Object.values(log).some(value =>
            String(value ?? "").toLowerCase().includes(query)
        )
    );

    const tbody = $("logsTableBody");
    if (!tbody) return;

    if (!filtered.length) {
        tbody.innerHTML =
            '<tr><td colspan="4" class="empty-state">No matching visitor logs.</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(logRowHTML).join("");
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
        return allLogs;
    }
}

export function initVisitorLogs() {
    const search = $("logSearch");
    const refreshButton = $("refreshLogsButton");

    if (search) {
        search.addEventListener("input", () => renderLogs(allLogs));
    }

    if (refreshButton) {
        refreshButton.addEventListener("click", loadLogs);
    }
}
