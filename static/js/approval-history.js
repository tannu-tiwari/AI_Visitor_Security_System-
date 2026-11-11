import { $, escapeHTML, fetchJSON, setText } from "./utils.js";
import { emptyStateHTML } from "./empty-state.js";
import { setButtonLoading } from "./loading.js";
import { createPaginator } from "./pagination.js";
import { toast } from "./toast.js";

// Approval History panel.
//
// Decisions are derived on the server from stored registrations, so only
// real, recorded decisions appear. Older approvals may predate the
// Decision By / Decision At fields; those are shown as "Not recorded" and
// never invented. Search and paging happen in the browser because the
// dataset is small and delivered as one JSON array.

let allDecisions = null; // null until the first successful load
let lastFiltered = [];
let paginator = null;

const SEARCH_FIELDS = [
    "Name",
    "Registration ID",
    "Host",
    "Approval Status",
    "Decision By",
    "Rejection Reason"
];

function field(record, key) {
    if (key === "Registration ID") {
        return record["Registration ID"] ?? record.registration_id ?? "";
    }
    return record[key] ?? record[key.toLowerCase()] ?? "";
}

function getPaginator() {
    if (!paginator) {
        paginator = createPaginator({
            controlsId: "approvalHistoryPager",
            summaryId: "approvalHistorySummary",
            pageSize: 10,
            label: "decisions",
            onChange: () => renderDecisions(lastFiltered)
        });
    }
    return paginator;
}

function searchQuery() {
    const input = $("approvalHistorySearch");
    return input ? input.value.trim() : "";
}

function decisionOrder(record) {
    return String(field(record, "Decision At") ||
        field(record, "Registration Time") || "");
}

function filterDecisions() {
    const query = searchQuery().toLowerCase();

    const filtered = !query
        ? allDecisions.slice()
        : allDecisions.filter(record => {
            const haystack = SEARCH_FIELDS
                .map(key => String(field(record, key) ?? ""))
                .join(" ")
                .toLowerCase();
            return haystack.includes(query);
        });

    return filtered.sort((a, b) =>
        decisionOrder(b).localeCompare(decisionOrder(a))
    );
}

function statusBadgeClass(status) {
    const value = String(status ?? "").toLowerCase();
    if (value === "approved") return "badge-green";
    if (value === "rejected") return "badge-red";
    return "badge-gray";
}

function decisionDate(value) {
    const text = String(value ?? "").trim();
    return text ? text.replace("T", " ") : "Not recorded";
}

function decisionRowHTML(record) {
    const name = String(field(record, "Name") ?? "") || "Unknown";
    const id = String(field(record, "Registration ID") ?? "") || "—";
    const host = String(field(record, "Host") ?? "") || "Not provided";
    const status = String(field(record, "Approval Status") ?? "") || "Unknown";
    const decidedBy = String(field(record, "Decision By") ?? "") ||
        "Not recorded";
    const decidedAt = decisionDate(field(record, "Decision At"));
    const reason = status.toLowerCase() === "rejected"
        ? (String(field(record, "Rejection Reason") ?? "") || "Not recorded")
        : "—";

    return `
        <tr>
            <td>
                <strong>${escapeHTML(name)}</strong><br>
                <span class="table-subtext">${escapeHTML(id)}</span>
            </td>
            <td>${escapeHTML(host)}</td>
            <td>${escapeHTML(decidedBy)}</td>
            <td>
                <span class="badge ${statusBadgeClass(status)}">
                    ${escapeHTML(status)}
                </span>
            </td>
            <td>${escapeHTML(decidedAt)}</td>
            <td>${escapeHTML(reason)}</td>
        </tr>
    `;
}

function emptyRow(state) {
    return `<tr><td colspan="6">${state}</td></tr>`;
}

function renderDecisions(decisions) {
    lastFiltered = decisions;

    const view = getPaginator().paginate(decisions);
    setText("approvalHistoryBadge",
        (allDecisions ? allDecisions.length : 0) + " Decisions");

    const tbody = $("approvalHistoryBody");
    if (!tbody) return;

    if (!view.total) {
        tbody.innerHTML = emptyRow(
            searchQuery()
                ? emptyStateHTML({
                    icon: "🔍",
                    title: "No matching approval decisions",
                    message: "No decisions match the current search.",
                    action: { label: "Clear Search", id: "clearApprovalSearch" }
                })
                : emptyStateHTML({
                    icon: "🗂",
                    title: "No approval decisions yet",
                    message: "Approved and rejected visitor requests will appear here once a host acts on them.",
                    action: {
                        label: "Review Pending Requests",
                        href: "/approvals"
                    }
                })
        );
        return;
    }

    tbody.innerHTML = view.items.map(decisionRowHTML).join("");
}

function applyFilters() {
    if (!Array.isArray(allDecisions)) return;
    renderDecisions(filterDecisions());
}

export async function loadApprovalHistory() {
    try {
        const data = await fetchJSON("/api/approval-history");
        allDecisions = Array.isArray(data)
            ? data
            : (data.history || data.approvals || []);

        applyFilters();
        return allDecisions;
    } catch (error) {
        console.error("Could not load approval history:", error);
        allDecisions = null;

        const tbody = $("approvalHistoryBody");
        if (tbody) {
            tbody.innerHTML = emptyRow(emptyStateHTML({
                icon: "⚠️",
                title: "Could not load approval history",
                message: "The server did not respond. The table will retry automatically.",
                variant: "error"
            }));
        }

        setText("approvalHistorySummary", "Could not load approval history.");
        setText("approvalHistoryBadge", "Error");
        return null;
    }
}

export function initApprovalHistory() {
    const search = $("approvalHistorySearch");
    if (search) {
        // Debounce so typing does not re-render the table on every keypress.
        let searchTimer;
        search.addEventListener("input", () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                getPaginator().reset();
                applyFilters();
            }, 200);
        });
    }

    const tbody = $("approvalHistoryBody");
    if (tbody) {
        tbody.addEventListener("click", event => {
            if (event.target.id === "clearApprovalSearch") {
                if (search) {
                    search.value = "";
                    search.focus();
                }
                getPaginator().reset();
                applyFilters();
            }
        });
    }

    const refreshButton = $("refreshApprovalHistoryButton");
    if (refreshButton) {
        refreshButton.addEventListener("click", async () => {
            setButtonLoading(refreshButton, true, "Refreshing...");
            try {
                const result = await loadApprovalHistory();
                if (result === null) {
                    toast.error("Could not refresh approval history.");
                }
            } finally {
                setButtonLoading(refreshButton, false);
            }
        });
    }
}
