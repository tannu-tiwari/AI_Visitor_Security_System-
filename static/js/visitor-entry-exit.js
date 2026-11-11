import { $, fetchJSON, escapeHTML, setText } from "./utils.js";
import { confirmDialog } from "./modal.js";
import { toast } from "./toast.js";
import { setButtonLoading } from "./loading.js";
import { emptyStateHTML } from "./empty-state.js";

export async function loadInsideVisitors() {
    try {
        const data = await fetchJSON("/api/open-visitors");
        const visitors = Array.isArray(data)
            ? data
            : (data.visitors || data.open_visitors || []);

        setText("insideVisitors", visitors.length);
        setText("insideBadge", visitors.length + " Visitors");

        const list = $("insideList");
        if (!list) return visitors;

        if (!visitors.length) {
            list.innerHTML = emptyStateHTML({
                icon: "🏢",
                title: "No visitors currently inside",
                message: "When an approved visitor is marked as entered, they will appear here."
            });
            return visitors;
        }

        list.innerHTML = visitors.map(visitor => {
            const name = visitor.Name || visitor.name ||
                visitor["Visitor Name"] || "Unknown";
            const time = visitor["Entry Time"] ||
                visitor.entry_time || visitor.time || "";

            return `
                <div class="list-item">
                    <h4>${escapeHTML(name)}</h4>
                    <p>Entry time: ${escapeHTML(time || "Not available")}</p>
                    <div class="list-actions">
                        <button class="button button-danger small-button"
                            data-exit-name="${escapeHTML(name)}"
                            data-exit-time="${escapeHTML(time)}">
                            Mark Exit
                        </button>
                    </div>
                </div>
            `;
        }).join("");

        return visitors;
    } catch (error) {
        console.error("Could not load open visitors:", error);
        const list = $("insideList");
        if (list) {
            list.innerHTML = emptyStateHTML({
                icon: "⚠️",
                title: "Could not load inside visitors",
                message: "The server did not respond. The list will retry automatically.",
                variant: "error"
            });
        }
        return null;
    }
}

export async function loadApprovedVisitors() {
    try {
        const data = await fetchJSON("/api/registrations");
        const registrations = Array.isArray(data)
            ? data
            : (data.registrations || data.visitors || []);
        const approved = registrations.filter(visitor =>
            String(visitor["Approval Status"] || visitor.approval_status || "")
                .toLowerCase() === "approved"
        );

        setText("approvedBadge", approved.length + " Approved");

        const list = $("approvedList");
        if (!list) return approved;

        if (!approved.length) {
            list.innerHTML = emptyStateHTML({
                icon: "👥",
                title: "No approved visitors",
                message: "Visitors approved by their host will appear here, ready to be marked as entered.",
                action: { label: "Review Approvals", href: "/approvals" }
            });
            return approved;
        }

        list.innerHTML = approved.map(visitor => {
            const name = visitor.Name || visitor.name || "Visitor";
            const id = visitor["Registration ID"] || visitor.registration_id || visitor.id || "";
            const purpose = visitor.Purpose || visitor.purpose || "";
            const host = visitor.Host || visitor.host || "";

            return `
                <div class="list-item">
                    <h4>${escapeHTML(name)}</h4>
                    <p>Purpose: ${escapeHTML(purpose)}<br>
                       Host: ${escapeHTML(host)}<br>
                       Status: <span class="badge badge-green">Approved</span></p>
                    <div class="list-actions">
                        <button class="button button-primary small-button"
                            data-entry-name="${escapeHTML(name)}"
                            data-entry-id="${escapeHTML(id)}"
                            data-entry-purpose="${escapeHTML(purpose)}"
                            data-entry-host="${escapeHTML(host)}">
                            Mark Entry
                        </button>
                    </div>
                </div>
            `;
        }).join("");

        return approved;
    } catch (error) {
        console.error("Could not load approved visitors:", error);
        const list = $("approvedList");
        if (list) {
            list.innerHTML = emptyStateHTML({
                icon: "⚠️",
                title: "Could not load approved visitors",
                message: "The server did not respond. The list will retry automatically.",
                variant: "error"
            });
        }
        return null;
    }
}

export function initVisitorEntryExit() {
    const approvedList = $("approvedList");
    const insideList = $("insideList");

    if (approvedList) {
        approvedList.addEventListener("click", async event => {
            const button = event.target.closest("[data-entry-name]");
            if (!button) return;

            const name = button.dataset.entryName;
            const purpose = button.dataset.entryPurpose || "";
            const host = button.dataset.entryHost || "";

            const details = [];
            if (host && host !== "Not provided") details.push("Host: " + host);
            if (purpose && purpose !== "Not provided") {
                details.push("Purpose: " + purpose);
            }

            setButtonLoading(button, true);

            try {
                let response;

                const confirmed = await confirmDialog({
                    title: "Confirm Visitor Entry",
                    description: "Mark " + name + " as entered?" +
                        (details.length ? " " + details.join(" · ") + "." : "") +
                        " Their entry time will be recorded and they will " +
                        "appear under Currently Inside.",
                    confirmLabel: "Mark Entry",
                    onConfirm: async () => {
                        response = await fetchJSON("/mark-entry", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ name })
                        });

                        if (response && response.success === false) {
                            throw new Error(
                                response.message ||
                                "Entry could not be recorded. Please check the Flask backend."
                            );
                        }
                    }
                });

                if (!confirmed) return;

                toast.success(
                    (response && response.message) ||
                    name + " marked as entered."
                );
                await Promise.all([
                    loadInsideVisitors(),
                    loadApprovedVisitors()
                ]);
            } catch (error) {
                console.error("Entry error:", error);
                toast.error(
                    error.message ||
                    "Entry could not be recorded. Please check the Flask backend."
                );
            } finally {
                setButtonLoading(button, false);
            }
        });
    }

    if (insideList) {
        insideList.addEventListener("click", async event => {
            const button = event.target.closest("[data-exit-name]");
            if (!button) return;

            const name = button.dataset.exitName;
            const entryTime = button.dataset.exitTime || "";

            setButtonLoading(button, true);

            try {
                let response;

                const confirmed = await confirmDialog({
                    title: "Confirm Visitor Exit",
                    description: "Mark " + name + " as exited?" +
                        (entryTime && entryTime !== "Not available"
                            ? " They entered at " + entryTime + "."
                            : "") +
                        " Their entry record will be closed.",
                    confirmLabel: "Mark Exit",
                    danger: true,
                    onConfirm: async () => {
                        response = await fetchJSON("/mark-exit", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ name })
                        });

                        if (response && response.success === false) {
                            throw new Error(
                                response.message ||
                                "Exit could not be recorded. Please check the Flask backend."
                            );
                        }
                    }
                });

                if (!confirmed) return;

                toast.success(
                    (response && response.message) ||
                    name + " marked as exited."
                );
                await loadInsideVisitors();
            } catch (error) {
                console.error("Exit error:", error);
                toast.error(
                    error.message ||
                    "Exit could not be recorded. Please check the Flask backend."
                );
            } finally {
                setButtonLoading(button, false);
            }
        });
    }
}
