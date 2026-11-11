import { $, fetchJSON } from "./utils.js";

let capturedFilename = "";

function retryCameraFeed() {
    const feed = document.getElementById("liveCameraFeed");
    const error = document.getElementById("cameraFeedError");

    error.style.display = "none";
    feed.style.display = "block";

    // Reconnect to the Flask video stream.
    feed.src = "/video_feed?t=" + Date.now();
}

async function captureVisitorPhoto() {
    const feed = $("liveCameraFeed");
    const button = $("captureVisitorButton");
    if (!feed || !feed.complete || !feed.naturalWidth || !feed.naturalHeight) {
        alert("Camera feed is not ready. Please wait and try again.");
        return;
    }

    button.disabled = true;
    button.textContent = "Capturing...";

    try {
        const canvas = $("captureCanvas");
        canvas.width = feed.naturalWidth;
        canvas.height = feed.naturalHeight;
        canvas.getContext("2d").drawImage(feed, 0, 0);

        const imageData = canvas.toDataURL("image/jpeg", 0.9);
        const result = await fetchJSON("/save-capture", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image: imageData })
        });

        if (!result.success || !result.filename) {
            throw new Error(result.message || "Image could not be saved.");
        }

        capturedFilename = result.filename;
        $("captureFilename").value = capturedFilename;
        $("capturedPhotoPreview").src = imageData;
        $("capturedPhotoPreview").style.display = "block";
        $("capturePanel").style.display = "block";
        $("captureStatus").textContent = "Photo saved: " + capturedFilename;
        $("registrationForm").style.display = "block";
        $("registrationForm").scrollIntoView({ behavior: "smooth", block: "start" });
        if (!$("visitorName").value.trim()) $("visitorName").focus();
    } catch (error) {
        console.error("Capture failed:", error);
        alert("Photo capture failed: " + error.message);
    } finally {
        button.disabled = false;
        button.textContent = "Capture Visitor";
    }
}

export function retakeVisitorPhoto() {
    capturedFilename = "";
    $("captureFilename").value = "";
    $("capturedPhotoPreview").removeAttribute("src");
    $("capturedPhotoPreview").style.display = "none";
    $("capturePanel").style.display = "none";
    $("registrationForm").style.display = "none";
    $("captureStatus").textContent = "";
}

export async function checkCamera() {
    $("cameraStatus").textContent = "Checking camera...";
    $("cameraDot").className = "status-dot";
    $("cameraBadge").className = "badge badge-gray";
    $("cameraBadge").textContent = "Checking";

    try {
        const data = await fetchJSON("/camera-status");

        if (data.camera_available) {
            $("cameraStatus").textContent = "Camera Available";
            $("cameraDot").className = "status-dot online";
            $("cameraBadge").className = "badge badge-green";
            $("cameraBadge").textContent = "Available";
        } else {
            $("cameraStatus").textContent = "Camera Unavailable";
            $("cameraDot").className = "status-dot offline";
            $("cameraBadge").className = "badge badge-red";
            $("cameraBadge").textContent = "Unavailable";
        }
    } catch (error) {
        $("cameraStatus").textContent = "Status Unavailable";
        $("cameraDot").className = "status-dot offline";
        $("cameraBadge").className = "badge badge-red";
        $("cameraBadge").textContent = "Error";
    }
}

export function initCamera() {
    $("retryCameraButton").addEventListener("click", retryCameraFeed);
    $("restartFeedButton").addEventListener("click", retryCameraFeed);
    $("checkCameraButton").addEventListener("click", checkCamera);
    $("captureVisitorButton").addEventListener("click", captureVisitorPhoto);
    $("retakePhotoButton").addEventListener("click", retakeVisitorPhoto);
}
