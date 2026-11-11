import { escapeHTML } from "./utils.js";

// Shared empty/error state markup for every list, table and card grid.
//
// emptyStateHTML({
//     icon: "🕐",                              // emoji fits the existing design
//     title: "No pending approvals",           // short heading (required)
//     message: "New requests will appear...",  // one-line explanation
//     variant: "empty" | "error",              // error = failed request, not empty data
//     action: { label, href }                  // link action, or
//     action: { label, id }                    // button action (wire via delegation)
// })
//
// All text is escaped, so developer strings are safe to extend later.

export function emptyStateHTML({
    icon = "📭",
    title,
    message = "",
    action = null,
    variant = "empty"
} = {}) {
    let actionHTML = "";

    if (action && action.label) {
        const label = escapeHTML(action.label);
        if (action.href) {
            actionHTML =
                `<a class="button button-secondary small-button" href="${escapeHTML(action.href)}">${label}</a>`;
        } else {
            const id = action.id ? ` id="${escapeHTML(action.id)}"` : "";
            actionHTML =
                `<button type="button" class="button button-secondary small-button"${id}>${label}</button>`;
        }
    }

    const classes = "empty-state" + (variant === "error" ? " error" : "");

    return `
        <div class="${classes}" role="status">
            <div class="empty-icon" aria-hidden="true">${escapeHTML(icon)}</div>
            <h4>${escapeHTML(title || "Nothing here yet")}</h4>
            ${message ? `<p>${escapeHTML(message)}</p>` : ""}
            ${actionHTML}
        </div>
    `;
}
