import { $, fetchJSON } from "./utils.js";

let hostsRequestId = 0;

function setStatus(id, message, isError = false) {
    const element = $(id);
    if (!element) {
        return;
    }

    element.textContent = message;
    element.classList.toggle("error", Boolean(message) && isError);
}

function setPlaceholder(select, message) {
    const option = new Option(message, "", true, true);
    option.disabled = true;
    select.replaceChildren(option);
}

function clearHosts(message) {
    const hostSelect = $("visitorHost");
    if (!hostSelect) {
        return;
    }

    setPlaceholder(hostSelect, message);
    hostSelect.disabled = true;
}

export function resetHostSelection() {
    hostsRequestId += 1;
    clearHosts("Select Department First");
    setStatus("hostStatus", "");

    const departmentSelect = $("visitorDepartment");
    if (departmentSelect) {
        departmentSelect.value = "";
    }
}

function applyDepartments(departments) {
    const departmentSelect = $("visitorDepartment");
    if (!departmentSelect) {
        return;
    }

    departmentSelect.replaceChildren();
    setPlaceholder(
        departmentSelect,
        departments.length ? "Select department" : "No departments available"
    );

    departments.forEach(department => {
        departmentSelect.add(new Option(department, department));
    });

    departmentSelect.disabled = departments.length === 0;

    if (departments.length) {
        setStatus("departmentStatus", "");
    } else {
        setStatus(
            "departmentStatus",
            "No active host accounts have a department yet.",
            true
        );
    }
}

async function loadDepartments() {
    const departmentSelect = $("visitorDepartment");
    if (!departmentSelect) {
        return;
    }

    departmentSelect.disabled = true;
    setPlaceholder(departmentSelect, "Loading departments...");
    clearHosts("Select Department First");
    setStatus("departmentStatus", "Loading departments...");

    try {
        const data = await fetchJSON("/api/departments");
        const departments = Array.isArray(data.departments)
            ? data.departments.filter(department =>
                typeof department === "string" && department.trim())
            : [];

        applyDepartments(departments);
    } catch (error) {
        applyDepartments([]);
        setPlaceholder(departmentSelect, "Unable to load departments");
        setStatus(
            "departmentStatus",
            "Could not load departments. Refresh the page to try again.",
            true
        );
    }
}

async function handleDepartmentChange() {
    const departmentSelect = $("visitorDepartment");
    if (!departmentSelect) {
        return;
    }

    const department = departmentSelect.value;
    const requestId = ++hostsRequestId;

    clearHosts("Select Department First");
    setStatus("hostStatus", "");

    if (!department) {
        return;
    }

    clearHosts("Loading hosts...");
    setStatus("hostStatus", "Loading hosts...");

    try {
        const data = await fetchJSON(
            "/api/hosts?department=" + encodeURIComponent(department)
        );

        if (requestId !== hostsRequestId) {
            return;
        }

        const hosts = Array.isArray(data.hosts) ? data.hosts : [];

        if (!hosts.length) {
            clearHosts("No hosts available in this department");
            setStatus(
                "hostStatus",
                "No active hosts are available in this department.",
                true
            );
            return;
        }

        const hostSelect = $("visitorHost");
        hostSelect.replaceChildren();
        setPlaceholder(hostSelect, "Select host");

        hosts.forEach(host => {
            hostSelect.add(new Option(host.full_name, String(host.id)));
        });

        hostSelect.disabled = false;
        setStatus("hostStatus", "");
    } catch (error) {
        if (requestId !== hostsRequestId) {
            return;
        }

        clearHosts("Unable to load hosts");
        setStatus(
            "hostStatus",
            "Could not load hosts for this department. Please try again.",
            true
        );
    }
}

export function initHostDepartmentDropdowns() {
    const departmentSelect = $("visitorDepartment");
    const hostSelect = $("visitorHost");
    const form = $("registrationForm");

    if (!departmentSelect || !hostSelect) {
        return;
    }

    departmentSelect.addEventListener("change", handleDepartmentChange);

    if (form) {
        form.addEventListener("reset", () => {
            window.setTimeout(resetHostSelection, 0);
        });
    }

    loadDepartments();
}
