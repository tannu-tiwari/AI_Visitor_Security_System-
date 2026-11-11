import { initVisitorApproval, loadApprovals } from "../visitor-approval.js";

initVisitorApproval();
loadApprovals();

// Keep the pending list current.
setInterval(loadApprovals, 10000);
