import { initVisitorLogs, loadLogs } from "../visitor-logs.js";

initVisitorLogs();
loadLogs();

// Keep the history table current without starting face recognition.
setInterval(loadLogs, 10000);
