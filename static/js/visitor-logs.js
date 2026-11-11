import { $, escapeHTML, fetchJSON } from "./utils.js";

let allLogs = [];

function renderLogs(logs) {
    const query = $("logSearch").value.trim().toLowerCase();

    const filtered = logs.filter(log =>
        Object.values(log).some(value =>
            String(value ?? "").toLowerCase().includes(query)
        )
    );

    if (!filtered.length) {
        $("logsTableBody").innerHTML =
            '<tr><td colspan="4" class="empty-state">No matching visitor logs.</td></tr>';
        return;
    }

    $("logsTableBody").innerHTML = filtered.map(log => {
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
    }).join("");
}

export async function loadLogs() {
    try {
        const data = await fetchJSON("/api/visitor-logs");

        if (Array.isArray(data)) {
            allLogs = data;
        } else {
            allLogs = data.logs || [];
            if (data.total_visitors !== undefined) {
                $("totalVisitors").textContent = data.total_visitors;
            }
            if (data.recognized !== undefined) {
                $("recognizedVisitors").textContent = data.recognized;
            }
            if (data.unknown !== undefined) {
                $("unknownVisitors").textContent = data.unknown;
            }
        }

        renderLogs(allLogs);
    } catch (error) {
        console.error("Could not load visitor logs:", error);
    }
}

export function initVisitorLogs() {
    $("logSearch").addEventListener("input", () => renderLogs(allLogs));
    $("refreshLogsButton").addEventListener("click", loadLogs);
}
