import { setButtonLoading } from "./loading.js";

// Reusable modal dialogs (confirmations + small forms) shared by every page.
// Replaces the native prompt()/confirm() flows with one dialog element that
// is built once and reconfigured on every call.
//
// confirmDialog({ title, description, ... })  -> Promise<boolean>
// formDialog({ title, description, fields })  -> Promise<object | null>
//
// - Cancelling (Cancel button, close button, Escape, backdrop click) resolves
//   with false / null and never calls `onConfirm`, so no API request is sent.
// - While `onConfirm` is awaited the dialog is "busy": every dismissal path is
//   blocked and the confirm button shows a loading spinner.
// - If `onConfirm` throws, the dialog closes and the promise rejects with that
//   error so the caller can show a failure notification.

let overlay = null;
let dialog = null;
let titleEl = null;
let descriptionEl = null;
let formEl = null;
let fieldsWrap = null;
let errorEl = null;
let cancelBtn = null;
let confirmBtn = null;
let closeBtn = null;
let state = null;

function buildDialog() {
    overlay = document.createElement("div");
    overlay.className = "modal-overlay";

    dialog = document.createElement("div");
    dialog.className = "modal-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-labelledby", "modal-title");
    dialog.setAttribute("aria-describedby", "modal-description");

    closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "modal-close";
    closeBtn.setAttribute("aria-label", "Close dialog");
    closeBtn.textContent = "×";

    titleEl = document.createElement("h3");
    titleEl.className = "modal-title";
    titleEl.id = "modal-title";

    descriptionEl = document.createElement("p");
    descriptionEl.className = "modal-description";
    descriptionEl.id = "modal-description";

    formEl = document.createElement("form");
    formEl.className = "modal-form";

    fieldsWrap = document.createElement("div");
    fieldsWrap.className = "modal-fields";

    errorEl = document.createElement("p");
    errorEl.className = "modal-error";

    const actions = document.createElement("div");
    actions.className = "modal-actions";

    cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "button button-secondary";

    confirmBtn = document.createElement("button");
    confirmBtn.type = "submit";
    confirmBtn.className = "button button-primary";

    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    formEl.appendChild(fieldsWrap);
    formEl.appendChild(errorEl);
    formEl.appendChild(actions);

    dialog.appendChild(closeBtn);
    dialog.appendChild(titleEl);
    dialog.appendChild(descriptionEl);
    dialog.appendChild(formEl);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    overlay.addEventListener("click", onBackdropClick);
    overlay.addEventListener("keydown", onKeyDown);
    formEl.addEventListener("submit", onSubmit);
    closeBtn.addEventListener("click", () => cancel());
    cancelBtn.addEventListener("click", () => cancel());
}

function buildField(field) {
    const group = document.createElement("div");
    group.className = "form-group" +
        (field.type === "textarea" ? " full" : "");

    const label = document.createElement("label");
    label.textContent = field.label || field.name;
    label.setAttribute("for", "modal-field-" + field.name);

    const input = document.createElement(
        field.type === "textarea" ? "textarea" : "input"
    );
    input.name = field.name;
    input.id = "modal-field-" + field.name;
    if (field.type !== "textarea") {
        input.type = field.type || "text";
    }
    if (field.placeholder) {
        input.placeholder = field.placeholder;
    }
    if (field.initialValue !== undefined) {
        input.value = field.initialValue;
    }

    const error = document.createElement("p");
    error.className = "field-error";

    group.appendChild(label);
    group.appendChild(input);
    group.appendChild(error);

    input.addEventListener("input", () => {
        error.textContent = "";
        error.classList.remove("visible");
        input.classList.remove("field-invalid");
        input.removeAttribute("aria-invalid");
    });

    return { group, input, error, config: field };
}

function openDialog(config, kind) {
    const cancelValue = kind === "confirm" ? false : null;

    if (!overlay) buildDialog();

    if (state) {
        console.warn("modal: a dialog is already open");
        return Promise.resolve(cancelValue);
    }

    return new Promise((resolve, reject) => {
        titleEl.textContent = config.title || "";
        descriptionEl.textContent = config.description || "";
        descriptionEl.style.display = config.description ? "" : "none";

        confirmBtn.textContent = config.confirmLabel || "Confirm";
        cancelBtn.textContent = config.cancelLabel || "Cancel";
        confirmBtn.className = "button " +
            (config.danger ? "button-danger" : "button-primary");

        fieldsWrap.replaceChildren();
        const fieldEls = (config.fields || []).map(buildField);
        for (const field of fieldEls) {
            fieldsWrap.appendChild(field.group);
        }
        fieldsWrap.style.display = fieldEls.length ? "" : "none";

        errorEl.textContent = "";
        errorEl.classList.remove("visible");

        setButtonLoading(confirmBtn, false);
        cancelBtn.disabled = false;
        closeBtn.disabled = false;

        overlay.classList.add("open");
        document.body.classList.add("modal-open");

        state = {
            kind,
            cancelValue,
            busy: false,
            resolved: false,
            resolve,
            reject,
            fieldEls,
            onConfirm: typeof config.onConfirm === "function"
                ? config.onConfirm
                : null,
            lastFocused: document.activeElement
        };

        const firstField = fieldEls[0] && fieldEls[0].input;
        if (firstField) {
            firstField.focus();
        } else if (config.danger) {
            cancelBtn.focus();
        } else {
            confirmBtn.focus();
        }
    });
}

function setBusy(busy) {
    if (!state) return;
    state.busy = busy;
    confirmBtn.disabled = busy;
    cancelBtn.disabled = busy;
    closeBtn.disabled = busy;
    overlay.classList.toggle("modal-busy", busy);
    setButtonLoading(confirmBtn, busy, "Processing...");
}

function teardown() {
    const finishedState = state;
    state = null;

    overlay.classList.remove("open");
    overlay.classList.remove("modal-busy");
    document.body.classList.remove("modal-open");

    setButtonLoading(confirmBtn, false);
    cancelBtn.disabled = false;
    closeBtn.disabled = false;

    if (finishedState.lastFocused &&
        typeof finishedState.lastFocused.focus === "function") {
        try {
            finishedState.lastFocused.focus();
        } catch (error) {
            // The element may have been removed from the page.
        }
    }
    return finishedState;
}

function cancel() {
    if (!state || state.busy || state.resolved) return;
    state.resolved = true;
    const finishedState = teardown();
    finishedState.resolve(finishedState.cancelValue);
}

function onBackdropClick(event) {
    if (!state || state.busy || state.resolved) return;
    if (event.target !== overlay) return;
    state.resolved = true;
    const finishedState = teardown();
    finishedState.resolve(finishedState.cancelValue);
}

function getFocusables() {
    const focusables = [closeBtn];
    for (const { input } of state.fieldEls) {
        focusables.push(input);
    }
    focusables.push(cancelBtn, confirmBtn);
    return focusables.filter(element => !element.disabled);
}

function onKeyDown(event) {
    if (!state || state.resolved) return;

    if (event.key === "Escape") {
        if (state.busy) return;
        event.preventDefault();
        cancel();
        return;
    }

    if (event.key === "Tab") {
        const focusables = getFocusables();
        if (!focusables.length) return;

        const current = focusables.indexOf(document.activeElement);
        let next;
        if (event.shiftKey) {
            next = current <= 0 ? focusables.length - 1 : current - 1;
        } else {
            next = current === -1 || current === focusables.length - 1
                ? 0
                : current + 1;
        }

        event.preventDefault();
        focusables[next].focus();
    }
}

function validateFields() {
    const values = {};
    let firstInvalid = null;

    for (const { input, error, config } of state.fieldEls) {
        const value = String(input.value ?? "").trim();
        let message = "";

        if (config.required && !value) {
            message = config.requiredMessage || "This field is required.";
        }

        if (!message && typeof config.validate === "function") {
            message = config.validate(value) || "";
        }

        error.textContent = message;
        error.classList.toggle("visible", !!message);
        input.classList.toggle("field-invalid", !!message);

        if (message) {
            input.setAttribute("aria-invalid", "true");
            if (!firstInvalid) firstInvalid = input;
        } else {
            input.removeAttribute("aria-invalid");
        }

        values[config.name] = value;
    }

    if (firstInvalid) {
        firstInvalid.focus();
        return null;
    }

    return values;
}

async function onSubmit(event) {
    event.preventDefault();
    if (!state || state.busy || state.resolved) return;

    const values = validateFields();
    if (values === null) return;

    if (!state.onConfirm) {
        state.resolved = true;
        const success = state.kind === "confirm" ? true : values;
        const finishedState = teardown();
        finishedState.resolve(success);
        return;
    }

    setBusy(true);
    try {
        await state.onConfirm(values);
        state.resolved = true;
        const success = state.kind === "confirm" ? true : values;
        const finishedState = teardown();
        finishedState.resolve(success);
    } catch (error) {
        state.resolved = true;
        const finishedState = teardown();
        finishedState.reject(
            error instanceof Error
                ? error
                : new Error(String(error && error.message || error))
        );
    }
}

export function confirmDialog(config) {
    return openDialog(config, "confirm");
}

export function formDialog(config) {
    return openDialog(config, "form");
}
