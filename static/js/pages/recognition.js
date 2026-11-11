import { $ } from "../utils.js";
import { checkCamera, initCameraFeed } from "../camera-feed.js";
import { loadLogs, logRowHTML } from "../visitor-logs.js";

function renderRecentEvents(logs) {
    const tbody = $("recentRecognitionBody");
    if (!tbody) return;

    const recent = logs.slice(0, 6);

    if (!recent.length) {
        tbody.innerHTML =
            '<tr><td colspan="4" class="empty-state">No recognition events yet.</td></tr>';
        return;
    }

    tbody.innerHTML = recent.map(logRowHTML).join("");
}

async function refreshRecognition() {
    const logs = await loadLogs();
    renderRecentEvents(logs);
}

initCameraFeed();
checkCamera();
refreshRecognition();

// Keep the recent events list current while this page is open.
setInterval(refreshRecognition, 10000);
