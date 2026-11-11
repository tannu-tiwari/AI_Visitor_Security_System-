const passwordInput = document.getElementById("password");
const passwordToggle = document.getElementById("passwordToggle");

if (passwordInput && passwordToggle) {
    passwordToggle.addEventListener("click", () => {
        const showing = passwordInput.type === "text";

        passwordInput.type = showing ? "password" : "text";
        passwordToggle.textContent = showing ? "Show" : "Hide";
        passwordToggle.setAttribute("aria-pressed", String(!showing));

        passwordInput.focus();
    });
}
