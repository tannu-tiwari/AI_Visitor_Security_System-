import { $ } from "../utils.js";
import { checkCamera, initCameraFeed } from "../camera-feed.js";
import { loadLogs, logRowHTML } from "../visitor-logs.js";
import { emptyStateHTML } from "../empty-state.js";

function renderRecentEvents(logs) {
    const tbody = $("recentRecognitionBody");
    if (!tbody) return;

    if (logs === null) {
        tbody.innerHTML = `<tr><td colspan="4">${emptyStateHTML({
            icon: "⚠️",
            title: "Could not load recognition events",
            message: "The server did not respond. This list will retry automatically.",
            variant: "error"
        })}</td></tr>`;
        return;
    }

    const recent = logs.slice(0, 6);

    if (!recent.length) {
        tbody.innerHTML = `<tr><td colspan="4">${emptyStateHTML({
            icon: "📖",
            title: "No recognition events yet",
            message: "Events will appear here once the camera feed identifies a face."
        })}</td></tr>`;
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
