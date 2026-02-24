"""GPIO hardware controller and mock implementation.

Real controller uses gpiozero for Raspberry Pi GPIO pins.
Mock controller logs actions for Windows/Mac development.
"""

import logging

logger = logging.getLogger(__name__)

# GPIO pin assignments (BCM numbering)
DOOR_LOCK_PIN = 17
FRIDGE_RELAY_PIN = 27
STATUS_LED_PIN = 22


class MockHardwareController:
    """Mock hardware controller for development on Windows/Mac."""

    def __init__(self):
        self._door_locked = True
        logger.info("[MOCK HW] Hardware controller initialized (mock mode)")

    def unlock_door(self) -> None:
        self._door_locked = False
        logger.info("[MOCK HW] Door UNLOCKED")

    def lock_door(self) -> None:
        self._door_locked = True
        logger.info("[MOCK HW] Door LOCKED")

    def is_door_locked(self) -> bool:
        return self._door_locked

    def set_status_led(self, on: bool) -> None:
        state = "ON" if on else "OFF"
        logger.info("[MOCK HW] Status LED %s", state)

    def fridge_power(self, on: bool) -> None:
        state = "ON" if on else "OFF"
        logger.info("[MOCK HW] Fridge power %s", state)


class PiHardwareController:
    """Real hardware controller for Raspberry Pi using gpiozero.

    Only instantiated on Raspberry Pi. Imports gpiozero at construction time.
    """

    def __init__(self):
        from gpiozero import OutputDevice

        self._door_lock = OutputDevice(DOOR_LOCK_PIN, active_high=False)
        self._fridge_relay = OutputDevice(FRIDGE_RELAY_PIN, active_high=True)
        self._status_led = OutputDevice(STATUS_LED_PIN, active_high=True)

        # Start with door locked, fridge on, LED on
        self._door_lock.off()  # off = locked (active_high=False)
        self._fridge_relay.on()
        self._status_led.on()
        logger.info("[PI HW] Hardware controller initialized (real GPIO)")

    def unlock_door(self) -> None:
        self._door_lock.on()
        logger.info("[PI HW] Door UNLOCKED (GPIO %d HIGH)", DOOR_LOCK_PIN)

    def lock_door(self) -> None:
        self._door_lock.off()
        logger.info("[PI HW] Door LOCKED (GPIO %d LOW)", DOOR_LOCK_PIN)

    def is_door_locked(self) -> bool:
        return not self._door_lock.is_active

    def set_status_led(self, on: bool) -> None:
        if on:
            self._status_led.on()
        else:
            self._status_led.off()
        logger.info("[PI HW] Status LED %s", "ON" if on else "OFF")

    def fridge_power(self, on: bool) -> None:
        if on:
            self._fridge_relay.on()
        else:
            self._fridge_relay.off()
        logger.info("[PI HW] Fridge power %s", "ON" if on else "OFF")
