"""NFC reader module for tap-to-pay.

Placeholder for NFC reader integration (ACR122U or PN532).
"""

import logging

logger = logging.getLogger(__name__)


class MockNFCReader:
    """Mock NFC reader for development."""

    def wait_for_tag(self, timeout: float = 5.0) -> dict | None:
        """Wait for an NFC tag. Returns None (no tag in mock mode)."""
        logger.info("[MOCK NFC] Waiting for tag (timeout=%.1fs) — mock, returning None", timeout)
        return None

    def close(self) -> None:
        logger.info("[MOCK NFC] Reader closed")


class PiNFCReader:
    """Real NFC reader using USB HID interface.

    TODO: Implement with pyscard or nfcpy when hardware is available.
    """

    def __init__(self):
        logger.info("[PI NFC] NFC reader initialized (stub — not yet implemented)")

    def wait_for_tag(self, timeout: float = 5.0) -> dict | None:
        # TODO: Implement real NFC tag reading
        logger.warning("[PI NFC] wait_for_tag not yet implemented")
        return None

    def close(self) -> None:
        pass


def get_nfc_reader():
    from hardware import IS_RASPBERRY_PI

    if IS_RASPBERRY_PI:
        return PiNFCReader()
    return MockNFCReader()
