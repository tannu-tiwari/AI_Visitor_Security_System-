import { $, fetchJSON } from "./utils.js";
import { toast } from "./toast.js";
import { setButtonLoading } from "./loading.js";

// Visitor photo capture for the registration flow. The live feed itself is
// handled by camera-feed.js; this module grabs a frame from the feed <img>,
// saves it through /save-capture and reveals the registration form.

let capturedFilename = "";

async function captureVisitorPhoto() {
    const feed = $("liveCameraFeed");
    const button = $("captureVisitorButton");
    if (!feed || !feed.complete || !feed.naturalWidth || !feed.naturalHeight) {
        toast.warning("Camera feed is not ready. Please wait and try again.");
        return;
    }

    setButtonLoading(button, true, "Capturing...");

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
        toast.error("Photo capture failed: " + error.message);
    } finally {
        setButtonLoading(button, false);
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

export function initPhotoCapture() {
    const captureButton = $("captureVisitorButton");
    const retakeButton = $("retakePhotoButton");

    if (captureButton) {
        captureButton.addEventListener("click", captureVisitorPhoto);
    }

    if (retakeButton) {
        retakeButton.addEventListener("click", retakeVisitorPhoto);
    }
}
