// Reusable toast notifications shared by every page.
//
// toast.success(message) / toast.error(...) / toast.warning(...) / toast.info(...)
//
// - Messages are inserted with textContent, so visitor data is always safe.
// - Toasts auto-dismiss after a few seconds and can be closed manually.
// - The stack is capped so notifications never cover the whole screen.

const DEFAULT_DURATION = 4500;
const ERROR_DURATION = 7000;
const MAX_VISIBLE = 5;

let container = null;

const ICONS = {
    success: "✓",
    error: "✕",
    warning: "!",
    info: "i"
};

function ensureContainer() {
    if (container) return container;
    container = document.createElement("div");
    container.className = "toast-container";
    container.setAttribute("aria-live", "polite");
    document.body.appendChild(container);
    return container;
}

export function showToast(message, type = "info", duration) {
    const parent = ensureContainer();

    const toast = document.createElement("div");
    const safeType = ICONS[type] ? type : "info";
    toast.className = "toast toast-" + safeType;

    const icon = document.createElement("span");
    icon.className = "toast-icon";
    icon.textContent = ICONS[safeType];

    const text = document.createElement("span");
    text.className = "toast-message";
    text.textContent = String(message ?? "");

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "toast-close";
    closeBtn.setAttribute("aria-label", "Dismiss notification");
    closeBtn.textContent = "×";

    toast.appendChild(icon);
    toast.appendChild(text);
    toast.appendChild(closeBtn);

    while (parent.children.length >= MAX_VISIBLE) {
        parent.removeChild(parent.firstChild);
    }

    parent.appendChild(toast);

    let dismissed = false;
    const dismiss = () => {
        if (dismissed) return;
        dismissed = true;
        toast.classList.add("toast-hide");
        setTimeout(() => toast.remove(), 250);
    };

    closeBtn.addEventListener("click", dismiss);

    const lifetime = duration ??
        (safeType === "error" ? ERROR_DURATION : DEFAULT_DURATION);
    if (lifetime > 0) {
        setTimeout(dismiss, lifetime);
    }

    return toast;
}

export const toast = {
    success: (message, duration) => showToast(message, "success", duration),
    error: (message, duration) => showToast(message, "error", duration),
    warning: (message, duration) => showToast(message, "warning", duration),
    info: (message, duration) => showToast(message, "info", duration)
};
