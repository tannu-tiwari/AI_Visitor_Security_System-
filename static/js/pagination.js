import { $ } from "./utils.js";

// Shared client-side paginator.
//
// Page data is already delivered by the existing APIs as one small JSON
// array, so paging is a presentation concern: filter/sort first, then hand
// the full array to paginate(). The paginator keeps the current page when
// possible, clamps it when records disappear, and resets to page 1 whenever
// the caller changes a search/filter (via reset()).
export function createPaginator({
    controlsId,
    summaryId = "",
    pageSize = 10,
    label = "records",
    onChange = null
}) {
    let page = 1;
    let total = 0;
    let totalPages = 1;
    let busy = false;

    function paint(start, end) {
        const summary = summaryId ? $(summaryId) : null;
        if (summary) {
            summary.textContent =
                "Showing " + start + "–" + end + " of " + total + " " + label;
        }

        const controls = $(controlsId);
        if (!controls) return;

        controls.innerHTML =
            '<button type="button" class="button button-secondary small-button"' +
            ' data-pager="prev"' + (page <= 1 ? " disabled" : "") +
            ">Previous</button>" +
            '<span class="pagination-status">Page ' + page + " of " +
            totalPages + "</span>" +
            '<button type="button" class="button button-secondary small-button"' +
            ' data-pager="next"' + (page >= totalPages ? " disabled" : "") +
            ">Next</button>";

        controls.setAttribute("aria-busy", "false");
        controls.classList.remove("pagination-busy");
    }

    function clamp() {
        totalPages = Math.max(1, Math.ceil(total / pageSize));
        if (page > totalPages) page = totalPages;
        if (page < 1) page = 1;
    }

    function paginate(items) {
        total = items.length;
        clamp();

        const startIndex = (page - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        const start = total ? startIndex + 1 : 0;
        const end = Math.min(endIndex, total);

        paint(start, end);

        return {
            items: items.slice(startIndex, endIndex),
            page: page,
            totalPages: totalPages,
            total: total,
            start: start,
            end: end
        };
    }

    function reset() {
        page = 1;
    }

    async function handleClick(event) {
        if (busy || typeof onChange !== "function") return;

        const button = event.target.closest("[data-pager]");
        if (!button) return;

        const direction = button.getAttribute("data-pager");
        const next = direction === "prev" ? page - 1 : page + 1;
        if (next < 1 || next > totalPages || next === page) return;

        page = next;

        const controls = $(controlsId);
        busy = true;
        if (controls) {
            controls.classList.add("pagination-busy");
            controls.setAttribute("aria-busy", "true");
        }

        try {
            await onChange(page);
        } catch (error) {
            console.error("Pagination update failed:", error);
        } finally {
            busy = false;
            if (controls) {
                controls.classList.remove("pagination-busy");
                controls.setAttribute("aria-busy", "false");
            }
        }
    }

    const controls = $(controlsId);
    if (controls) {
        controls.addEventListener("click", handleClick);
    }

    return {
        paginate: paginate,
        reset: reset,
        get page() {
            return page;
        },
        get total() {
            return total;
        }
    };
}
