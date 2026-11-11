import { initVisitorLogs, loadLogs } from "../visitor-logs.js";
import {
    initVisitorHistory,
    loadVisitorHistory
} from "../visitor-records.js";

initVisitorLogs();
initVisitorHistory();
loadLogs();
loadVisitorHistory();

// Keep both tables current without starting face recognition.
setInterval(loadLogs, 10000);
setInterval(loadVisitorHistory, 10000);
