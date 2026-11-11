import { $, fetchJSON, escapeHTML, setText } from "./utils.js";
import { loadApprovedVisitors } from "./visitor-entry-exit.js";
import { formDialog } from "./modal.js";
import { toast } from "./toast.js";
import { setButtonLoading } from "./loading.js";
import { emptyStateHTML } from "./empty-state.js";
import { createPaginator } from "./pagination.js";

let lastApprovals = [];
let paginator = null;

function getPaginator() {
    if (!paginator) {
        paginator = createPaginator({
            controlsId: "approvalPager",
            summaryId: "approvalSummary",
            pageSize: 10,
            label: "pending requests",
            onChange: () => renderApprovals(lastApprovals)
        });
    }
    return paginator;
}

function approvalCardHTML(visitor) {
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
                                data-decision="approved"
                                data-visitor-name="${escapeHTML(name)}"
                                data-visitor-host="${escapeHTML(host)}">
                                Approve
                            </button>

                            <button class="button button-danger small-button"
                                data-approval-id="${escapeHTML(id)}"
                                data-decision="rejected"
                                data-visitor-name="${escapeHTML(name)}"
                                data-visitor-host="${escapeHTML(host)}">
                                Reject
                            </button>
                        </div>
                    </div>
                </div>
            `;
}

function renderApprovals(approvals) {
    lastApprovals = approvals;
    setText("pendingBadge", approvals.length + " Pending");

    const list = $("approvalList");
    if (!list) return approvals;

    const view = getPaginator().paginate(approvals);

    if (!view.total) {
        list.innerHTML = emptyStateHTML({
            icon: "🕐",
            title: "No pending approvals",
            message: "New visitor requests will appear here for host review.",
            action: { label: "Register a Visitor", href: "/registration" }
        });
        return approvals;
    }

    list.innerHTML = view.items.map(approvalCardHTML).join("");
    return approvals;
}

export async function loadApprovals() {
    try {
        const data = await fetchJSON("/api/pending-approvals");
        const approvals = Array.isArray(data)
            ? data
            : (data.approvals || data.pending || []);

        renderApprovals(approvals);
        return approvals;
    } catch (error) {
        console.error("Approval loading error:", error);
        const list = $("approvalList");
        if (list) {
            list.innerHTML = emptyStateHTML({
                icon: "⚠️",
                title: "Could not load approvals",
                message: "The server did not respond. The list will retry automatically.",
                variant: "error"
            });
        }
        return null;
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
        const visitorName = button.dataset.visitorName || "this visitor";
        const visitorHost = button.dataset.visitorHost || "";

        if (!id) {
            toast.warning("Registration ID is missing.");
            return;
        }

        const rejecting = decision === "rejected";
        const description = (visitorHost && visitorHost !== "Not provided"
            ? visitorName + " — visiting " + visitorHost + ". "
            : visitorName + ". ") +
            (rejecting
                ? "Enter the host's name and the reason for rejecting this request."
                : "Enter the host's name to approve this request.");

        setButtonLoading(button, true);

        try {
            let response;

            const values = await formDialog({
                title: rejecting
                    ? "Reject Visitor Request"
                    : "Approve Visitor Request",
                description,
                confirmLabel: rejecting ? "Reject Visitor" : "Approve Visitor",
                danger: rejecting,
                fields: [
                    {
                        name: "decided_by",
                        label: "Your Name (Host / Decision Maker)",
                        type: "text",
                        required: true,
                        placeholder: "e.g. Dr. A. Mehta"
                    }
                ].concat(rejecting ? [
                    {
                        name: "rejection_reason",
                        label: "Rejection Reason",
                        type: "textarea",
                        required: true,
                        placeholder: "Why is this visitor being rejected?"
                    }
                ] : []),
                onConfirm: async (values) => {
                    response = await fetchJSON(
                        "/host-approval/" + encodeURIComponent(id) + "/" +
                        encodeURIComponent(decision),
                        {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                                decided_by: values.decided_by,
                                rejection_reason: values.rejection_reason || ""
                            })
                        }
                    );

                    if (response && response.success === false) {
                        throw new Error(
                            response.message ||
                            "Approval could not be updated. Check the backend."
                        );
                    }
                }
            });

            if (values === null) return;

            let message = (response && response.message) ||
                "Approval decision processed.";

            if (!response || response.success) {
                message += response && response.email_sent
                    ? " Email sent to the visitor."
                    : " Email could not be sent.";
            }

            toast.success(message);

            await loadApprovals();
            if ($("approvedList")) {
                await loadApprovedVisitors();
            }
        } catch (error) {
            console.error("Approval error:", error);
            toast.error(
                error.message ||
                "Approval could not be updated. Check the backend."
            );
        } finally {
            setButtonLoading(button, false);
        }
    });
}
