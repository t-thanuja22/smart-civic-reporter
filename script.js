document.addEventListener("DOMContentLoaded", function () {
  const mapEl = document.getElementById("map");
  if (!mapEl) return;

  const gpsStatus = document.getElementById("gps-status");
  const latInput = document.getElementById("latitude");
  const lonInput = document.getElementById("longitude");
  const locateBtn = document.getElementById("locate-btn");
  const addressInput = document.getElementById("address_text");
  const imageInput = document.getElementById("image-input");
  const preview = document.getElementById("preview");
  const stampHint = document.getElementById("stamp-hint");

  const DEFAULT_CENTER = [11.1271, 78.6569];
  const map = L.map("map").setView(DEFAULT_CENTER, 13);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  let marker = null;
  let originalImageFile = null;

  function setMarker(lat, lon) {
    latInput.value = lat;
    lonInput.value = lon;
    if (marker) {
      marker.setLatLng([lat, lon]);
    } else {
      marker = L.marker([lat, lon], { draggable: true }).addTo(map);
      marker.on("dragend", function () {
        const pos = marker.getLatLng();
        latInput.value = pos.lat;
        lonInput.value = pos.lng;
        gpsStatus.textContent =
          "Pin adjusted to " + pos.lat.toFixed(5) + ", " + pos.lng.toFixed(5);
        stampImageIfReady();
      });
    }
    stampImageIfReady();
  }

  function locateUser() {
    gpsStatus.textContent = "Detecting your location...";
    if (!navigator.geolocation) {
      gpsStatus.textContent = "Geolocation is not supported by this browser -- tap the map to set your location manually.";
      return;
    }
    navigator.geolocation.getCurrentPosition(
      function (position) {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        map.setView([lat, lon], 17);
        setMarker(lat, lon);
        gpsStatus.textContent =
          "Location captured (" + lat.toFixed(5) + ", " + lon.toFixed(5) +
          "). Drag the pin to fine-tune it.";
      },
      function () {
        gpsStatus.textContent =
          "Could not access GPS. Tap anywhere on the map to drop your pin manually.";
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }

  map.on("click", function (e) {
    setMarker(e.latlng.lat, e.latlng.lng);
    gpsStatus.textContent =
      "Pin set to " + e.latlng.lat.toFixed(5) + ", " + e.latlng.lng.toFixed(5);
  });

  if (locateBtn) locateBtn.addEventListener("click", locateUser);
  locateUser();
  setTimeout(function () { map.invalidateSize(); }, 200);

  function replaceFileInput(inputEl, blob, filename) {
    const dt = new DataTransfer();
    const file = new File([blob], filename, { type: blob.type });
    dt.items.add(file);
    inputEl.files = dt.files;
  }

  function stampImageIfReady() {
    if (!originalImageFile) return;
    if (!latInput.value || !lonInput.value) return;

    const img = new Image();
    const objectUrl = URL.createObjectURL(originalImageFile);
    img.onload = function () {
      const canvas = document.createElement("canvas");
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0);

      const barHeight = Math.max(56, Math.round(img.height * 0.09));
      ctx.fillStyle = "rgba(11, 34, 51, 0.72)";
      ctx.fillRect(0, img.height - barHeight, img.width, barHeight);

      ctx.fillStyle = "#ffffff";
      const fontSize = Math.max(14, Math.round(barHeight * 0.26));
      ctx.font = fontSize + "px Arial, sans-serif";

      const lat = parseFloat(latInput.value).toFixed(5);
      const lon = parseFloat(lonInput.value).toFixed(5);
      const now = new Date();
      const line1 = "Lat " + lat + "  |  Lon " + lon +
        (addressInput.value ? "  |  " + addressInput.value : "");
      const line2 = "Smart Civic Reporter  |  " + now.toLocaleString();

      ctx.fillText(line1, 14, img.height - barHeight + fontSize * 1.2);
      ctx.fillText(line2, 14, img.height - barHeight + fontSize * 2.5);

      canvas.toBlob(function (blob) {
        replaceFileInput(imageInput, blob, "geotagged_" + Date.now() + ".jpg");
        preview.src = canvas.toDataURL("image/jpeg", 0.9);
        preview.style.display = "block";
        stampHint.textContent = "Location and timestamp stamped onto the photo.";
      }, "image/jpeg", 0.9);

      URL.revokeObjectURL(objectUrl);
    };
    img.src = objectUrl;
  }

  const video = document.getElementById("camera-preview");
  const openCameraBtn = document.getElementById("open-camera-btn");
  const captureBtn = document.getElementById("capture-btn");
  const retakeBtn = document.getElementById("retake-btn");
  const cameraHint = document.getElementById("camera-hint");
  let cameraStream = null;

  async function openCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      cameraHint.textContent = "This browser/connection doesn't support live camera capture " +
        "(camera access needs https:// or localhost). Try opening this page as http://localhost:5000 instead.";
      return;
    }
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      video.srcObject = cameraStream;
      video.style.display = "block";
      preview.style.display = "none";
      openCameraBtn.style.display = "none";
      captureBtn.style.display = "inline-block";
      retakeBtn.style.display = "none";
      cameraHint.textContent = "Point the camera at the issue and tap Capture.";
    } catch (err) {
      cameraHint.textContent = "Could not access the camera -- please allow camera permission and try again.";
    }
  }

  function capturePhoto() {
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);

    if (cameraStream) cameraStream.getTracks().forEach(function (t) { t.stop(); });
    video.style.display = "none";
    captureBtn.style.display = "none";
    retakeBtn.style.display = "inline-block";

    canvas.toBlob(function (blob) {
      originalImageFile = new File([blob], "capture.jpg", { type: "image/jpeg" });
      if (latInput.value && lonInput.value) {
        stampImageIfReady();
      } else {
        preview.src = canvas.toDataURL("image/jpeg", 0.9);
        preview.style.display = "block";
        replaceFileInput(imageInput, blob, "capture_" + Date.now() + ".jpg");
        stampHint.textContent = "Photo will be stamped with the location once it's confirmed on the map.";
      }
    }, "image/jpeg", 0.9);
  }

  function retakePhoto() {
    preview.style.display = "none";
    retakeBtn.style.display = "none";
    openCameraBtn.style.display = "inline-block";
    stampHint.textContent = "";
    cameraHint.textContent = "Tap \"Open camera\" to take a live photo of the issue.";
  }

  if (openCameraBtn) openCameraBtn.addEventListener("click", openCamera);
  if (captureBtn) captureBtn.addEventListener("click", capturePhoto);
  if (retakeBtn) retakeBtn.addEventListener("click", retakePhoto);

  const recordBtn = document.getElementById("record-btn");
  const recordTimer = document.getElementById("record-timer");
  const voicePlayback = document.getElementById("voice-playback");
  const voiceInput = document.getElementById("voice-input");

  let mediaRecorder = null;
  let audioChunks = [];
  let recordSeconds = 0;
  let timerHandle = null;

  function formatTime(totalSeconds) {
    const m = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
    const s = String(totalSeconds % 60).padStart(2, "0");
    return m + ":" + s;
  }

  if (recordBtn) {
    recordBtn.addEventListener("click", async function () {
      if (!mediaRecorder || mediaRecorder.state === "inactive") {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          alert("Voice recording isn't supported on this browser.");
          return;
        }
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          mediaRecorder = new MediaRecorder(stream);
          audioChunks = [];
          mediaRecorder.ondataavailable = function (e) { audioChunks.push(e.data); };
          mediaRecorder.onstop = function () {
            const blob = new Blob(audioChunks, { type: "audio/webm" });
            replaceFileInput(voiceInput, blob, "voice_note_" + Date.now() + ".webm");
            voicePlayback.src = URL.createObjectURL(blob);
            voicePlayback.style.display = "block";
            stream.getTracks().forEach(function (t) { t.stop(); });
          };
          mediaRecorder.start();
          recordBtn.innerHTML = "&#9632; Stop recording";
          recordSeconds = 0;
          recordTimer.textContent = formatTime(recordSeconds);
          timerHandle = setInterval(function () {
            recordSeconds++;
            recordTimer.textContent = formatTime(recordSeconds);
          }, 1000);
        } catch (err) {
          alert("Microphone access was blocked. Please allow it to record a voice note.");
        }
      } else {
        mediaRecorder.stop();
        clearInterval(timerHandle);
        recordBtn.innerHTML = "&#9679; Start recording";
      }
    });
  }
});
