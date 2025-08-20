import os
import sys
import time
import threading
from typing import Optional, Tuple

from flask import Flask, Response, jsonify

try:
	import cv2
except Exception as e:
	raise RuntimeError(
		"OpenCV (cv2) is required. Install with `pip install opencv-python`"
	) from e


app = Flask(__name__)


class CameraWorker:
	"""Continuously captures frames from the default camera and keeps the latest JPEG in memory."""

	def __init__(
		self,
		index: int = 0,
		width: int = 1280,
		height: int = 720,
		fps: int = 10,
		jpeg_quality: int = 85,
	) -> None:
		self.index = index
		self.width = width
		self.height = height
		self.fps = fps
		self.jpeg_quality = jpeg_quality

		self._cap: Optional[cv2.VideoCapture] = None
		self._lock = threading.Lock()
		self._latest_jpeg: Optional[bytes] = None
		self._latest_ts: float = 0.0
		self._running = False
		self._thread: Optional[threading.Thread] = None

	def _open_capture(self) -> cv2.VideoCapture:
		# Prefer AVFoundation backend on macOS for reliability
		if sys.platform == "darwin":
			cap = cv2.VideoCapture(self.index, cv2.CAP_AVFOUNDATION)
		else:
			cap = cv2.VideoCapture(self.index)

		if not cap.isOpened():
			raise RuntimeError("Unable to open camera. Check permissions and index.")

		# Try to set resolution and fps (may be ignored by some drivers)
		cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
		cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
		cap.set(cv2.CAP_PROP_FPS, self.fps)
		return cap

	def start(self) -> None:
		if self._running:
			return
		self._running = True
		self._cap = self._open_capture()
		self._thread = threading.Thread(target=self._run, daemon=True)
		self._thread.start()

	def stop(self) -> None:
		self._running = False
		if self._thread:
			self._thread.join(timeout=2)
		if self._cap:
			try:
				self._cap.release()
			except Exception:
				pass

	def _reopen(self) -> None:
		try:
			if self._cap:
				self._cap.release()
		finally:
			self._cap = self._open_capture()

	def _encode_jpeg(self, frame) -> Optional[bytes]:
		params = [int(cv2.IMWRITE_JPEG_QUALITY), int(self.jpeg_quality)]
		ok, buf = cv2.imencode(".jpg", frame, params)
		if not ok:
			return None
		return buf.tobytes()

	def _run(self) -> None:
		delay = max(0.0, 1.0 / float(self.fps))
		failures = 0
		while self._running:
			if not self._cap or not self._cap.isOpened():
				# Try to reopen with backoff
				time.sleep(min(1 + failures, 5))
				try:
					self._reopen()
					failures = 0
				except Exception:
					failures += 1
					continue

			ok, frame = self._cap.read()
			if not ok or frame is None:
				failures += 1
				if failures % 10 == 0:
					# Periodically attempt to reopen on repeated failures
					try:
						self._reopen()
						failures = 0
					except Exception:
						pass
				time.sleep(0.05)
				continue

			failures = 0
			jpeg = self._encode_jpeg(frame)
			if jpeg is not None:
				with self._lock:
					self._latest_jpeg = jpeg
					self._latest_ts = time.time()

			time.sleep(delay)

	def get_latest(self) -> Tuple[Optional[bytes], float]:
		with self._lock:
			return self._latest_jpeg, self._latest_ts


# Configuration via environment variables
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "1920"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "1080"))
FRAME_FPS = int(os.getenv("FRAME_FPS", "10"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "85"))

camera = CameraWorker(
	index=CAMERA_INDEX,
	width=FRAME_WIDTH,
	height=FRAME_HEIGHT,
	fps=FRAME_FPS,
	jpeg_quality=JPEG_QUALITY,
)
camera.start()


@app.get("/health")
def health():
	latest, ts = camera.get_latest()
	return jsonify(
		{
			"ok": True,
			"has_frame": latest is not None,
			"timestamp": ts,
			"camera_index": CAMERA_INDEX,
			"width": FRAME_WIDTH,
			"height": FRAME_HEIGHT,
			"fps": FRAME_FPS,
		}
	)


@app.get("/latest.jpg")
def latest_jpg():
	jpeg, _ = camera.get_latest()
	if jpeg is None:
		return jsonify({"error": "No frame available yet"}), 503
	return Response(jpeg, mimetype="image/jpeg")


def main():
	host = os.getenv("HOST", "0.0.0.0")
	port = int(os.getenv("PORT", "5001"))
	# Threaded allows concurrent requests; debug off for production
	app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
	try:
		main()
	finally:
		camera.stop()

