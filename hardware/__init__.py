"""Hardware abstraction layer.

Detects platform and returns real GPIO/Camera/NFC controllers on Raspberry Pi,
or mock implementations on Windows/Mac for development.
"""

import platform
import logging

logger = logging.getLogger(__name__)

IS_RASPBERRY_PI = platform.machine().startswith("aarch64") or platform.machine().startswith("arm")


def get_controller():
    """Return the appropriate hardware controller for the current platform.

    On Raspberry Pi: returns real GPIO controller using gpiozero.
    On Windows/Mac: returns a mock controller that logs actions to console.
    """
    if IS_RASPBERRY_PI:
        try:
            from hardware.gpio import PiHardwareController
            logger.info("Running on Raspberry Pi — using real hardware controller")
            return PiHardwareController()
        except ImportError:
            logger.warning("gpiozero not available on Pi — falling back to mock")
            from hardware.gpio import MockHardwareController
            return MockHardwareController()
    else:
        logger.info("Running on %s — using mock hardware controller", platform.system())
        from hardware.gpio import MockHardwareController
        return MockHardwareController()
