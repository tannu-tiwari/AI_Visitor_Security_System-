import { $, escapeHTML, fetchJSON } from "../utils.js";
import { confirmDialog, formDialog } from "../modal.js";
import { emptyStateHTML } from "../empty-state.js";
import { setButtonLoading } from "../loading.js";
import { toast } from "../toast.js";

const ROLE_OPTIONS = [
    { value: "admin", label: "Administrator" },
    { value: "security", label: "Security Guard" },
    { value: "host", label: "Host" }
];

let users = [];
let searchTimer;

function userFields(user = null) {
    const editing = user !== null;
    const fields = [
        {
            name: "full_name",
            label: "Full Name",
            required: true,
            initialValue: editing ? user.full_name : ""
        },
        {
            name: "email",
            label: "Email",
            type: "email",
            initialValue: editing ? (user.email || "") : ""
        },
        {
            name: "role",
            label: "Role",
            type: "select",
            required: true,
            placeholder: "Select role",
            options: ROLE_OPTIONS,
            initialValue: editing ? (user.role || "") : ""
        },
        {
            name: "department",
            label: "Department",
            initialValue: editing ? (user.department || "") : ""
        },
        {
            name: "password",
            label: editing ? "New Password (leave blank to keep)" : "Password",
            type: "password",
            required: !editing
        }
    ];

    if (editing) {
        return fields;
    }

    return [
        {
            name: "username",
            label: "Username",
            required: true
        },
        ...fields
    ];
}

function payloadFrom(values, editing) {
    const payload = {
        full_name: values.full_name,
        email: values.email,
        role: values.role,
        department: values.department || ""
    };

    if (values.password) {
        payload.password = values.password;
    }

    if (!editing) {
        payload.username = values.username;
        payload.password = values.password;
    }

    return payload;
}

function statusBadge(user) {
    return user.is_active
        ? '<span class="badge badge-green">Active</span>'
        : '<span class="badge badge-gray">Inactive</span>';
}

function userRowHTML(user) {
    const name = user.full_name || user.username || "Unknown";
    const department = user.department || "—";
    const email = user.email || "—";

    return `
        <tr>
            <td>
                <strong>${escapeHTML(name)}</strong><br>
                <span class="table-subtext">Created ${escapeHTML(user.created_at || "unknown")}</span>
            </td>
            <td>${escapeHTML(user.username || "")}</td>
            <td>${escapeHTML(email)}</td>
            <td>${escapeHTML(user.role_label || user.role || "Unassigned")}</td>
            <td>${escapeHTML(department)}</td>
            <td>${statusBadge(user)}</td>
            <td>
                <div class="list-actions">
                    <button class="button button-secondary small-button"
                        data-edit-user="${user.id}">Edit</button>
                    <button class="button ${user.is_active ? "button-danger" : "button-primary"} small-button"
                        data-toggle-user="${user.id}">
                        ${user.is_active ? "Deactivate" : "Activate"}
                    </button>
                </div>
            </td>
        </tr>
    `;
}

function renderUsers() {
    const tbody = $("usersBody");
    if (!tbody) return;

    const query = ($("userSearch")?.value || "").trim().toLowerCase();
    const filtered = query
        ? users.filter(user => [
            user.full_name,
            user.username,
            user.email,
            user.role,
            user.role_label,
            user.department
        ].some(value => String(value || "").toLowerCase().includes(query)))
        : users;

    if (!filtered.length) {
        tbody.innerHTML = `<tr><td colspan="7">${emptyStateHTML({
            icon: "👤",
            title: query ? "No matching accounts" : "No accounts found",
            message: query
                ? "No account matches the current search."
                : "Create the first account to get started."
        })}</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(userRowHTML).join("");
}

async function loadUsers() {
    const tbody = $("usersBody");
    if (!tbody) return;

    try {
        const data = await fetchJSON("/api/users");
        users = Array.isArray(data.users) ? data.users : [];
        renderUsers();
    } catch (error) {
        console.error("Could not load users:", error);
        tbody.innerHTML = `<tr><td colspan="7">${emptyStateHTML({
            icon: "⚠️",
            title: "Could not load accounts",
            message: error.message || "The server did not respond.",
            variant: "error"
        })}</td></tr>`;
    }
}

async function openCreateDialog() {
    try {
        await formDialog({
            title: "Add User",
            description: "Create an administrator, security guard or host account.",
            confirmLabel: "Create User",
            fields: userFields(),
            onConfirm: async values => {
                const response = await fetchJSON("/api/users", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payloadFrom(values, false))
                });

                if (!response.success) {
                    throw new Error(response.message || "User could not be created.");
                }

                toast.success(response.message || "User created.");
            }
        });

        await loadUsers();
    } catch (error) {
        toast.error(error.message || "User could not be created.");
    }
}

async function openEditDialog(user) {
    try {
        await formDialog({
            title: "Edit User",
            description: "Update this account's details, role or password.",
            confirmLabel: "Save Changes",
            fields: userFields(user),
            onConfirm: async values => {
                const response = await fetchJSON(
                    "/api/users/" + encodeURIComponent(user.id),
                    {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payloadFrom(values, true))
                    }
                );

                if (!response.success) {
                    throw new Error(response.message || "User could not be updated.");
                }

                toast.success(response.message || "User updated.");
            }
        });

        await loadUsers();
    } catch (error) {
        toast.error(error.message || "User could not be updated.");
    }
}

async function toggleUser(user) {
    const activating = !user.is_active;
    const confirmed = await confirmDialog({
        title: activating ? "Activate User" : "Deactivate User",
        description: activating
            ? `Allow ${user.full_name || user.username} to log in again?`
            : `Prevent ${user.full_name || user.username} from logging in? Their history is kept.`,
        confirmLabel: activating ? "Activate" : "Deactivate",
        danger: !activating
    });

    if (!confirmed) return;

    try {
        const response = await fetchJSON(
            "/api/users/" + encodeURIComponent(user.id),
            {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_active: activating })
            }
        );

        if (!response.success) {
            throw new Error(response.message || "User could not be updated.");
        }

        toast.success(response.message || "User updated.");
        await loadUsers();
    } catch (error) {
        toast.error(error.message || "User could not be updated.");
    }
}

const addButton = $("addUserButton");
if (addButton) {
    addButton.addEventListener("click", async () => {
        setButtonLoading(addButton, true, "Opening...");
        try {
            await openCreateDialog();
        } finally {
            setButtonLoading(addButton, false);
        }
    });
}

const refreshButton = $("refreshUsersButton");
if (refreshButton) {
    refreshButton.addEventListener("click", async () => {
        setButtonLoading(refreshButton, true, "Refreshing...");
        try {
            await loadUsers();
        } finally {
            setButtonLoading(refreshButton, false);
        }
    });
}

const search = $("userSearch");
if (search) {
    search.addEventListener("input", () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(renderUsers, 200);
    });
}

const tbody = $("usersBody");
if (tbody) {
    tbody.addEventListener("click", event => {
        const editButton = event.target.closest("[data-edit-user]");
        if (editButton) {
            const user = users.find(item => item.id === Number(editButton.dataset.editUser));
            if (user) openEditDialog(user);
            return;
        }

        const toggleButton = event.target.closest("[data-toggle-user]");
        if (toggleButton) {
            const user = users.find(item => item.id === Number(toggleButton.dataset.toggleUser));
            if (user) toggleUser(user);
        }
    });
}

loadUsers();
