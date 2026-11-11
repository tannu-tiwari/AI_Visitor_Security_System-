import { $ } from "./utils.js";
import { checkCamera, initCamera } from "./camera.js";
import { initVisitorRegistration } from "./visitor-registration.js";
import { loadLogs, initVisitorLogs } from "./visitor-logs.js";
import { loadApprovals, initVisitorApproval } from "./visitor-approval.js";
import {
    loadInsideVisitors,
    loadApprovedVisitors,
    initVisitorEntryExit
} from "./visitor-entry-exit.js";

async function refreshDashboard() {
    await Promise.all([
        loadLogs(),
        loadInsideVisitors(),
        loadApprovals(),
        loadApprovedVisitors(),
        checkCamera()
    ]);
}

initCamera();
initVisitorRegistration();
initVisitorLogs();
initVisitorApproval();
initVisitorEntryExit();

$("refreshButton").addEventListener("click", refreshDashboard);

refreshDashboard();

// Refresh dashboard data periodically.
// This does not start continuous face recognition.
setInterval(() => {
    loadLogs();
    loadInsideVisitors();
    loadApprovals();
    loadApprovedVisitors();
}, 10000);
