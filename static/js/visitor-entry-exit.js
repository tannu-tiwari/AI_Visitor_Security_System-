import { $, fetchJSON, escapeHTML, setText } from "./utils.js";

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
            list.innerHTML =
                '<div class="empty-state">No open entry records.</div>';
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
                            data-exit-name="${escapeHTML(name)}">
                            Mark Exit
                        </button>
                    </div>
                </div>
            `;
        }).join("");

        return visitors;
    } catch (error) {
        const list = $("insideList");
        if (list) {
            list.innerHTML =
                '<div class="empty-state">Could not load open visitor records.</div>';
        }
        return [];
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
            list.innerHTML =
                '<div class="empty-state">No approved visitors waiting for entry.</div>';
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
                            data-entry-id="${escapeHTML(id)}">
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
            list.innerHTML =
                '<div class="empty-state">Could not load approved visitors.</div>';
        }
        return [];
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
            if (!confirm("Mark " + name + " as entered?")) return;

            button.disabled = true;
            try {
                const response = await fetchJSON("/mark-entry", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name })
                });
                alert(response.message || "Entry request sent.");
                await Promise.all([loadInsideVisitors(), loadApprovedVisitors()]);
            } catch (error) {
                alert("Entry could not be recorded. Please check the Flask backend.");
            } finally {
                button.disabled = false;
            }
        });
    }

    if (insideList) {
        insideList.addEventListener("click", async event => {
            const button = event.target.closest("[data-exit-name]");
            if (!button) return;

            const name = button.dataset.exitName;
            if (!confirm("Mark " + name + " as exited?")) return;

            try {
                const response = await fetchJSON("/mark-exit", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name })
                });

                alert(response.message || "Exit request sent.");
                await loadInsideVisitors();
            } catch (error) {
                alert("Exit could not be recorded. Please check the Flask backend.");
            }
        });
    }
}
