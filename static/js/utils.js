export const $ = (id) => document.getElementById(id);

export function setText(id, value) {
    const element = $(id);
    if (element) {
        element.textContent = String(value);
    }
}

export function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}

export async function fetchJSON(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => null);

    if (!response.ok) {
        const message = data && (data.message || data.error);
        throw new Error(
            message || "Request failed: " + response.status
        );
    }

    return data;
}

export function showFeedback(element, message, success) {
    element.textContent = message;
    element.className = "feedback " + (success ? "success" : "error");
}
