"""Tests for hardware/gpio.py — MockHardwareController operations."""

import pytest
from hardware.gpio import MockHardwareController

pytestmark = pytest.mark.unit


class TestMockHardwareController:
    def test_initial_state_locked(self):
        hw = MockHardwareController()
        assert hw.is_door_locked() is True

    def test_unlock_door(self):
        hw = MockHardwareController()
        hw.unlock_door()
        assert hw.is_door_locked() is False

    def test_lock_door(self):
        hw = MockHardwareController()
        hw.unlock_door()
        hw.lock_door()
        assert hw.is_door_locked() is True

    def test_toggle_door(self):
        hw = MockHardwareController()
        hw.unlock_door()
        assert hw.is_door_locked() is False
        hw.lock_door()
        assert hw.is_door_locked() is True

    def test_set_status_led(self):
        hw = MockHardwareController()
        # Should not raise
        hw.set_status_led(True)
        hw.set_status_led(False)

    def test_fridge_power(self):
        hw = MockHardwareController()
        # Should not raise
        hw.fridge_power(True)
        hw.fridge_power(False)
