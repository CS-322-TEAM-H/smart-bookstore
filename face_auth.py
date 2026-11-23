"""Basic camera enrollment + LBPH face-match prototype, not production-grade security.

Requires: pip install opencv-contrib-python
Press Q in the camera window to cancel. No passwords or PINs are used.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path


class FaceAuthError(Exception):
    pass


def _dependencies():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise FaceAuthError("Install camera support: pip install opencv-contrib-python") from exc
    if not hasattr(cv2, "face") or not hasattr(cv2.face, "LBPHFaceRecognizer_create"):
        raise FaceAuthError("OpenCV contrib is required. Install 'opencv-contrib-python' (not only 'opencv-python').")
    return cv2, np


def _capture(number=1):
    cv2, np = _dependencies()
    cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
    if cascade.empty():
        raise FaceAuthError("Face detector could not be loaded.")
    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
    cap = cv2.VideoCapture(0, backend)
    if not cap.isOpened():
        cap.release()
        raise FaceAuthError("Camera unavailable. Check Windows camera permissions and other apps.")
    samples = []
    frame_index = 0
    start = time.monotonic()
    try:
        while len(samples) < number:
            if time.monotonic() - start > 35:
                raise FaceAuthError("Face scan timed out. Try again with brighter lighting.")
            ok, frame = cap.read()
            if not ok:
                continue
            frame_index += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(75, 75))
            display = frame.copy()
            if len(faces) == 1:
                x, y, w, h = faces[0]
                cv2.rectangle(display, (x, y), (x+w, y+h), (35, 160, 45), 2)
                if frame_index % 5 == 0:
                    cropped = cv2.resize(gray[y:y+h, x:x+w], (120, 120))
                    samples.append(cv2.equalizeHist(cropped))
            cv2.putText(display, f"Face scan: {len(samples)}/{number} | Q = cancel", (12, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.67, (255,255,255), 2)
            cv2.imshow("Lumina - Face Recognition", display)
            if (cv2.waitKey(60) & 0xFF) in (ord("q"), 27):
                raise FaceAuthError("Face scan cancelled.")
        return np.stack(samples)
    except cv2.error as exc:
        raise FaceAuthError(f"Camera window error: {exc}") from exc
    finally:
        cap.release()
        try:
            cv2.destroyWindow("Lumina - Face Recognition")
        except cv2.error:
            pass


def enroll(user_id, storage_folder):
    cv2, np = _dependencies()
    folder = Path(storage_folder)
    folder.mkdir(parents=True, exist_ok=True)
    samples = _capture(12)
    profile_path = folder / f"user_{user_id}.npz"
    np.savez_compressed(profile_path, samples=samples)
    return str(profile_path)


def verify(profile_path):
    cv2, np = _dependencies()
    profile = Path(profile_path)
    if not profile.is_file():
        raise FaceAuthError("Stored face profile is missing.")
    stored = np.load(profile, allow_pickle=False)["samples"]
    if stored.ndim != 3 or len(stored) < 3:
        raise FaceAuthError("Face profile is invalid. Re-enrollment is required.")
    sample = _capture(1)[0]
    model = cv2.face.LBPHFaceRecognizer_create()
    model.train([s for s in stored], np.zeros(len(stored), dtype=np.int32))
    label, distance = model.predict(sample)
    # Lower LBPH distance is a better match. This threshold needs empirical testing.
    return label == 0 and distance <= 62.0, float(distance)
