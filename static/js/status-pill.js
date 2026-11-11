import { $, fetchJSON } from "./utils.js";

// Updates the camera status pill in the shared page header (base.html).
// Runs once on every page; the Face Recognition page additionally uses
// camera-feed.js for its own camera badge and control buttons.
async function updateCameraPill() {
    const status = $("cameraStatus");
    const dot = $("cameraDot");

    if (!status || !dot) return;

    status.textContent = "Checking camera...";
    dot.className = "status-dot";

    try {
        const data = await fetchJSON("/camera-status");

        if (data.camera_available) {
            status.textContent = "Camera Available";
            dot.className = "status-dot online";
        } else {
            status.textContent = "Camera Unavailable";
            dot.className = "status-dot offline";
        }
    } catch (error) {
        status.textContent = "Status Unavailable";
        dot.className = "status-dot offline";
    }
}

updateCameraPill();
