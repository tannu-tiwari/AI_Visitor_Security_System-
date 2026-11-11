import { $, fetchJSON, escapeHTML, setText } from "./utils.js";
import { loadApprovedVisitors } from "./visitor-entry-exit.js";

export async function loadApprovals() {
    try {
        const data = await fetchJSON("/api/pending-approvals");
        const approvals = Array.isArray(data)
            ? data
            : (data.approvals || data.pending || []);

        setText("pendingBadge", approvals.length + " Pending");

        const list = $("approvalList");
        if (!list) return approvals;

        if (!approvals.length) {
            list.innerHTML =
                '<div class="empty-state">No pending approvals.</div>';
            return approvals;
        }

        list.innerHTML = approvals.map(visitor => {
            const name = visitor.Name || visitor.name || "Visitor";
            const phone = visitor.Phone || visitor.phone || "Not provided";
            const email = visitor.Email || visitor.email || "Not provided";
            const purpose = visitor.Purpose || visitor.purpose || "Not provided";
            const host = visitor.Host || visitor.host || "Not provided";
            const department = visitor.Department ||
                visitor.department || "Not provided";
            const photo = visitor["Photo Filename"] || visitor.photo || "";
            const registrationTime = visitor["Registration Time"] ||
                visitor.registration_time || "Not provided";
            const id = visitor["Registration ID"] ||
                visitor.registration_id || visitor.id || "";

            return `
                <div class="approval-card">
                    <div class="approval-photo">
                        ${photo ? `
                            <img
                                src="/visitor-captures/${encodeURIComponent(photo)}"
                                alt="Visitor photo of ${escapeHTML(name)}"
                                onerror="this.outerHTML='<div class=&quot;photo-missing&quot;>No visitor photo available.</div>'"
                            >
                        ` : `
                            <div class="photo-missing">No visitor photo available.</div>
                        `}
                    </div>

                    <div class="approval-info">
                        <h4>${escapeHTML(name)}</h4>

                        <p>
                            Phone: ${escapeHTML(phone)}<br>
                            Email: ${escapeHTML(email)}<br>
                            Purpose: ${escapeHTML(purpose)}<br>
                            Host: ${escapeHTML(host)}<br>
                            Department: ${escapeHTML(department)}<br>
                            Registered: ${escapeHTML(registrationTime)}
                        </p>

                        <div class="list-actions">
                            <button class="button button-primary small-button"
                                data-approval-id="${escapeHTML(id)}"
                                data-decision="approved">
                                Approve
                            </button>

                            <button class="button button-danger small-button"
                                data-approval-id="${escapeHTML(id)}"
                                data-decision="rejected">
                                Reject
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join("");

        return approvals;

    } catch (error) {
        console.error("Approval loading error:", error);
        const list = $("approvalList");
        if (list) {
            list.innerHTML =
                '<div class="empty-state">Could not load host approvals.</div>';
        }
        return [];
    }
}

export function initVisitorApproval() {
    const list = $("approvalList");
    if (!list) return;

    list.addEventListener("click", async event => {
        const button = event.target.closest("[data-approval-id]");
        if (!button) return;

        const id = button.dataset.approvalId;
        const decision = button.dataset.decision;

        if (!id) {
            alert("Registration ID is missing.");
            return;
        }

        const decidedBy = prompt("Enter the host's name:");

        if (!decidedBy || !decidedBy.trim()) {
            alert("Host name is required.");
            return;
        }

        let rejectionReason = "";

        if (decision === "rejected") {
            rejectionReason = prompt("Enter the reason for rejection:");

            if (!rejectionReason || !rejectionReason.trim()) {
                alert("A rejection reason is required.");
                return;
            }
        }

        button.disabled = true;

        try {
            const response = await fetchJSON(
                "/host-approval/" + encodeURIComponent(id) + "/" +
                encodeURIComponent(decision),
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        decided_by: decidedBy.trim(),
                        rejection_reason: rejectionReason.trim()
                    })
                }
            );

            let message = response.message || "Approval decision processed.";

            if (response.success) {
                message += response.email_sent
                    ? " Email sent to the visitor."
                    : " Email could not be sent.";
            }

            alert(message);

            if (response.success) {
                await loadApprovals();
                await loadApprovedVisitors();
            }

        } catch (error) {
            console.error("Approval error:", error);
            alert("Approval could not be updated. Check the backend.");
        } finally {
            button.disabled = false;
        }
    });
}
