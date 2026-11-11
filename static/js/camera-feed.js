import { $, fetchJSON, setText } from "./utils.js";

// Live camera feed handling: reconnect, status checks and the header pill.
// The photo capture half of the old camera.js lives in photo-capture.js.

function retryCameraFeed() {
    const feed = document.getElementById("liveCameraFeed");
    const error = document.getElementById("cameraFeedError");

    if (!feed || !error) return;

    error.style.display = "none";
    feed.style.display = "block";

    // Reconnect to the Flask video stream.
    feed.src = "/video_feed?t=" + Date.now();
}

export async function checkCamera() {
    const dot = $("cameraDot");
    const badge = $("cameraBadge");

    setText("cameraStatus", "Checking camera...");
    if (dot) dot.className = "status-dot";
    if (badge) {
        badge.className = "badge badge-gray";
        badge.textContent = "Checking";
    }

    try {
        const data = await fetchJSON("/camera-status");

        if (data.camera_available) {
            setText("cameraStatus", "Camera Available");
            if (dot) dot.className = "status-dot online";
            if (badge) {
                badge.className = "badge badge-green";
                badge.textContent = "Available";
            }
        } else {
            setText("cameraStatus", "Camera Unavailable");
            if (dot) dot.className = "status-dot offline";
            if (badge) {
                badge.className = "badge badge-red";
                badge.textContent = "Unavailable";
            }
        }
    } catch (error) {
        setText("cameraStatus", "Status Unavailable");
        if (dot) dot.className = "status-dot offline";
        if (badge) {
            badge.className = "badge badge-red";
            badge.textContent = "Error";
        }
    }
}

export function initCameraFeed() {
    const retryButton = $("retryCameraButton");
    const restartButton = $("restartFeedButton");
    const checkButton = $("checkCameraButton");

    if (retryButton) retryButton.addEventListener("click", retryCameraFeed);
    if (restartButton) restartButton.addEventListener("click", retryCameraFeed);
    if (checkButton) checkButton.addEventListener("click", checkCamera);
}
