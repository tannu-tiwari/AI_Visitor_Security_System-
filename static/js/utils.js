export const $ = (id) => document.getElementById(id);

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
    if (!response.ok) {
        throw new Error("Request failed: " + response.status);
    }
    return response.json();
}

export function showFeedback(element, message, success) {
    element.textContent = message;
    element.className = "feedback " + (success ? "success" : "error");
}
