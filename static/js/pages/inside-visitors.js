import {
    initVisitorEntryExit,
    loadApprovedVisitors,
    loadInsideVisitors
} from "../visitor-entry-exit.js";

initVisitorEntryExit();
loadApprovedVisitors();
loadInsideVisitors();

// Keep both lists current.
setInterval(() => {
    loadApprovedVisitors();
    loadInsideVisitors();
}, 10000);
