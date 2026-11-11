import {
    initApprovalHistory,
    loadApprovalHistory
} from "../approval-history.js";

initApprovalHistory();
loadApprovalHistory();

// Keep the decision list current; the current page is preserved by the
// paginator unless records were removed.
setInterval(loadApprovalHistory, 10000);
