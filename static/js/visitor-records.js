import { $, escapeHTML, fetchJSON, setText } from "./utils.js";
import { emptyStateHTML } from "./empty-state.js";
import { createPaginator } from "./pagination.js";

// Visitor Records panel on the Visitor History page.
//
// Data comes from /api/registrations (every registered visitor) joined with
// /api/open-visitors (visitors currently inside). Filtering happens fully in
// the browser: the dataset is small, already delivered as one JSON array,
// and this keeps filter changes instant without extra API round-trips.

let allRecords = null; // null until the first successful load
let insideNames = new Set();
let paginator = null;

function getPaginator() {
    if (!paginator) {
        paginator = createPaginator({
            controlsId: "historyPager",
            summaryId: "historySummary",
            pageSize: 10,
            label: "records",
            onChange: applyFilters
        });
    }
    return paginator;
}

function resetAndFilter() {
    getPaginator().reset();
    applyFilters();
}

// Registration fields covered by the free-text search box.
const SEARCH_FIELDS = [
    "Name",
    "Phone",
    "Email",
    "Registration ID",
    "Host",
    "Department",
    "Purpose"
];

// Registration data uses human-readable keys; accept lower-case fallbacks too.
function field(record, key) {
    if (key === "Registration ID") {
        return record["Registration ID"] ?? record.registration_id ?? "";
    }
    if (key === "Registration Time") {
        return record["Registration Time"] ?? record.registration_time ?? "";
    }
    if (key === "Approval Status") {
        return record["Approval Status"] ?? record.approval_status ?? "";
    }
    return record[key] ?? record[key.toLowerCase()] ?? "";
}

// A select with no usable value (e.g. before its options exist) is
// treated as "all", matching the browser default for these filters.
function filterValue(id) {
    const element = $(id);
    return element && element.value ? element.value : "all";
}

function filtersActive() {
    const search = $("historySearch");
    return Boolean(
        (search && search.value.trim()) ||
        filterValue("historyApprovalFilter") !== "all" ||
        filterValue("historyDepartmentFilter") !== "all" ||
        filterValue("historyInsideFilter") !== "all" ||
        ($("historyStartDate") && $("historyStartDate").value) ||
        ($("historyEndDate") && $("historyEndDate").value)
    );
}

function getFilteredRecords() {
    const search = $("historySearch");
    const query = search ? search.value.trim().toLowerCase() : "";
    const approval = filterValue("historyApprovalFilter");
    const department = filterValue("historyDepartmentFilter");
    const inside = filterValue("historyInsideFilter");
    const start = $("historyStartDate") ? $("historyStartDate").value : "";
    const end = $("historyEndDate") ? $("historyEndDate").value : "";

    // An invalid range (start after end) shows an inline error and the date
    // part of the filter is simply not applied.
    let datesUsable = true;
    const dateError = $("historyDateError");
    if (start && end && start > end) {
        datesUsable = false;
        if (dateError) {
            dateError.textContent =
                "Start date must be on or before the end date.";
        }
    } else if (dateError) {
        dateError.textContent = "";
    }

    return allRecords.filter(record => {
        if (query) {
            const haystack = SEARCH_FIELDS
                .map(key => String(field(record, key) ?? ""))
                .join(" ")
                .toLowerCase();
            if (!haystack.includes(query)) return false;
        }

        if (approval !== "all") {
            const status = String(field(record, "Approval Status") ?? "")
                .toLowerCase();
            if (status !== approval) return false;
        }

        if (department !== "all" &&
            String(field(record, "Department") ?? "") !== department) {
            return false;
        }

        if (inside !== "all") {
            const isInside = insideNames.has(String(field(record, "Name") ?? ""));
            if (inside === "inside" && !isInside) return false;
            if (inside === "outside" && isInside) return false;
        }

        // "Registration Time" is stored as "YYYY-MM-DD HH:MM:SS", so the ISO
        // date prefix compares correctly as a string. Both bounds included.
        if (datesUsable && (start || end)) {
            const day = String(field(record, "Registration Time") ?? "")
                .slice(0, 10);
            if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return false;
            if (start && day < start) return false;
            if (end && day > end) return false;
        }

        return true;
    });
}

function statusBadgeClass(status) {
    const value = String(status ?? "").toLowerCase();
    if (value === "approved") return "badge-green";
    if (value === "rejected") return "badge-red";
    return "badge-orange";
}

function recordRowHTML(record) {
    const name = String(field(record, "Name") ?? "") || "Unknown";
    const id = String(field(record, "Registration ID") ?? "") || "—";
    const phone = String(field(record, "Phone") ?? "") || "Not provided";
    const email = String(field(record, "Email") ?? "") || "Not provided";
    const host = String(field(record, "Host") ?? "") || "Not provided";
    const department = String(field(record, "Department") ?? "") || "Not provided";
    const purpose = String(field(record, "Purpose") ?? "") || "Not provided";
    const registeredAt = String(field(record, "Registration Time") ?? "") ||
        "Not available";
    const status = String(field(record, "Approval Status") ?? "") || "Pending";
    const isInside = insideNames.has(name);

    return `
        <tr>
            <td>
                <strong>${escapeHTML(name)}</strong><br>
                <span class="table-subtext">${escapeHTML(id)}</span>
            </td>
            <td>
                ${escapeHTML(phone)}<br>
                <span class="table-subtext">${escapeHTML(email)}</span>
            </td>
            <td>${escapeHTML(host)}</td>
            <td>${escapeHTML(department)}</td>
            <td>${escapeHTML(purpose)}</td>
            <td>${escapeHTML(registeredAt)}</td>
            <td>
                <span class="badge ${statusBadgeClass(status)}">
                    ${escapeHTML(status)}
                </span>
            </td>
            <td>
                ${isInside
                    ? '<span class="badge badge-green">Inside</span>'
                    : '<span class="badge badge-gray">—</span>'}
            </td>
        </tr>
    `;
}

function emptyRow(state) {
    return `<tr><td colspan="8">${state}</td></tr>`;
}

function renderRecords(records) {
    const tbody = $("historyTableBody");
    if (!tbody) return;

    if (!records.length) {
        tbody.innerHTML = emptyRow(
            filtersActive()
                ? emptyStateHTML({
                    icon: "🔍",
                    title: "No matching visitor records",
                    message: "No registrations match the current search and filters.",
                    action: { label: "Clear Filters", id: "clearHistoryFilters" }
                })
                : emptyStateHTML({
                    icon: "📝",
                    title: "No visitor registrations yet",
                    message: "Registered visitors and their approval status will appear here.",
                    action: { label: "Register a Visitor", href: "/registration" }
                })
        );
        return;
    }

    tbody.innerHTML = records.map(recordRowHTML).join("");
}

function applyFilters() {
    if (!Array.isArray(allRecords)) return;

    const filtered = getFilteredRecords();

    // Newest registrations first, then paginate the sorted result.
    filtered.sort((a, b) =>
        String(field(b, "Registration Time") ?? "")
            .localeCompare(String(field(a, "Registration Time") ?? ""))
    );

    const view = getPaginator().paginate(filtered);
    renderRecords(view.items);
    setText("historyCountBadge", allRecords.length + " Total");
}

function refreshDepartmentOptions() {
    const select = $("historyDepartmentFilter");
    if (!select) return;

    const previous = select.value;

    const departments = [...new Set(allRecords
        .map(record => String(field(record, "Department") ?? "").trim())
        .filter(Boolean)
    )].sort((a, b) => a.localeCompare(b));

    select.innerHTML =
        '<option value="all">All Departments</option>' +
        departments
            .map(department =>
                '<option value="' + escapeHTML(department) + '">' +
                escapeHTML(department) + "</option>")
            .join("");

    // Keep the current selection when the data still contains it,
    // otherwise fall back to the All Departments option.
    select.value = departments.includes(previous) ? previous : "all";
}

export function clearHistoryFilters() {
    const search = $("historySearch");
    if (search) search.value = "";

    ["historyApprovalFilter", "historyDepartmentFilter", "historyInsideFilter"]
        .forEach(id => {
            const select = $(id);
            if (select) select.value = "all";
        });

    ["historyStartDate", "historyEndDate"].forEach(id => {
        const input = $(id);
        if (input) input.value = "";
    });

    const dateError = $("historyDateError");
    if (dateError) dateError.textContent = "";

    resetAndFilter();
}

export async function loadVisitorHistory() {
    try {
        const [registrations, openData] = await Promise.all([
            fetchJSON("/api/registrations"),
            fetchJSON("/api/open-visitors")
        ]);

        allRecords = Array.isArray(registrations)
            ? registrations
            : (registrations.registrations || []);

        const openVisitors = (openData && openData.visitors) || [];
        insideNames = new Set(openVisitors
            .map(visitor => String(
                visitor.Name || visitor.name || visitor["Visitor Name"] || ""
            ).trim())
            .filter(Boolean));

        refreshDepartmentOptions();
        applyFilters();
        return allRecords;
    } catch (error) {
        console.error("Could not load visitor history:", error);
        allRecords = null;

        const tbody = $("historyTableBody");
        if (tbody) {
            tbody.innerHTML = emptyRow(emptyStateHTML({
                icon: "⚠️",
                title: "Could not load visitor records",
                message: "The server did not respond. The table will retry automatically.",
                variant: "error"
            }));
        }

        setText("historySummary", "Could not load visitor records.");
        setText("historyCountBadge", "Error");
        return null;
    }
}

export function initVisitorHistory() {
    const search = $("historySearch");
    if (search) {
        // Debounce so typing does not re-render the table on every keypress.
        let searchTimer;
        search.addEventListener("input", () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(resetAndFilter, 200);
        });
    }

    ["historyApprovalFilter", "historyDepartmentFilter", "historyInsideFilter"]
        .forEach(id => {
            const select = $(id);
            if (select) select.addEventListener("change", resetAndFilter);
        });

    ["historyStartDate", "historyEndDate"].forEach(id => {
        const input = $(id);
        if (input) input.addEventListener("change", resetAndFilter);
    });

    const clearButton = $("clearHistoryButton");
    if (clearButton) {
        clearButton.addEventListener("click", () => {
            clearHistoryFilters();
            if (search) search.focus();
        });
    }

    const tbody = $("historyTableBody");
    if (tbody) {
        tbody.addEventListener("click", event => {
            if (event.target.id === "clearHistoryFilters") {
                clearHistoryFilters();
            }
        });
    }
}
