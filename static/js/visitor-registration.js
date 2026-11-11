import { $, fetchJSON, showFeedback } from "./utils.js";
import { retakeVisitorPhoto } from "./camera.js";
import { loadApprovals } from "./visitor-approval.js";

export function initVisitorRegistration() {
    $("registrationForm").addEventListener("submit", async event => {
        event.preventDefault();

        const form = event.currentTarget;
        const feedback = $("registrationFeedback");
        const submitButton = form.querySelector('button[type="submit"]');
        const formData = new FormData(form);
        const payload = Object.fromEntries(formData.entries());

        if (!payload.capture_filename) {
            showFeedback(feedback, "Please capture a visitor photo first.", false);
            return;
        }

        submitButton.disabled = true;
        submitButton.textContent = "Submitting...";

        try {
            const response = await fetchJSON("/register-visitor", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const success = response.success === true ||
                response.status === "success";

            showFeedback(
                feedback,
                response.message || (success
                    ? "Registration submitted."
                    : "Registration could not be completed."),
                success
            );

            if (success) {
                form.reset();
                retakeVisitorPhoto();
                await loadApprovals();
            }
        } catch (error) {
            showFeedback(
                feedback,
                "Registration failed. The backend route may expect form data instead of JSON, or the server may be unavailable.",
                false
            );
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = "Submit Registration";
        }
    });
}
