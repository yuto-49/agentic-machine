"""Camera module for inventory verification.

Uses picamera2 on Raspberry Pi, mock on other platforms.
"""

import logging

from hardware import IS_RASPBERRY_PI

logger = logging.getLogger(__name__)


class MockCamera:
    """Mock camera for development."""

    def capture(self, path: str = "capture.jpg") -> str:
        logger.info("[MOCK CAM] Captured image -> %s (mock)", path)
        return path

    def close(self) -> None:
        logger.info("[MOCK CAM] Camera closed")


class PiCamera:
    """Real Pi Camera using picamera2."""

    def __init__(self):
        from picamera2 import Picamera2

        self._cam = Picamera2()
        self._cam.configure(self._cam.create_still_configuration())
        logger.info("[PI CAM] Camera initialized")

    def capture(self, path: str = "capture.jpg") -> str:
        self._cam.start()
        self._cam.capture_file(path)
        self._cam.stop()
        logger.info("[PI CAM] Captured image -> %s", path)
        return path

    def close(self) -> None:
        self._cam.close()
        logger.info("[PI CAM] Camera closed")


def get_camera():
    if IS_RASPBERRY_PI:
        try:
            return PiCamera()
        except ImportError:
            logger.warning("picamera2 not available — using mock camera")
            return MockCamera()
    return MockCamera()
