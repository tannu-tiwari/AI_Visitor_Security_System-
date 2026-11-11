// Shared loading indicators.
//
// setButtonLoading(button, true, "Saving...") disables a button, adds a
// spinner and replaces its label; setButtonLoading(button, false) restores
// the original state. Use it around every asynchronous action so requests
// cannot be triggered twice and the UI always shows progress.

export function setButtonLoading(button, isLoading, loadingText) {
    if (!button) return;

    if (isLoading) {
        if (button.dataset.loadingOriginal === undefined) {
            button.dataset.loadingOriginal = button.textContent;
        }
        button.disabled = true;
        button.classList.add("button-loading");
        button.setAttribute("aria-busy", "true");
        button.textContent = loadingText || button.dataset.loadingOriginal;
    } else {
        button.disabled = false;
        button.classList.remove("button-loading");
        button.removeAttribute("aria-busy");
        if (button.dataset.loadingOriginal !== undefined) {
            button.textContent = button.dataset.loadingOriginal;
            delete button.dataset.loadingOriginal;
        }
    }
}
