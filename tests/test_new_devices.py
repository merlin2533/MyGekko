"""Tests for the device types that are read only: alarm system, heating, audio, trends."""
import json
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mygekko.const import DOMAIN

from .const import DEMO_CONFIG

DEMO = "custom_components/mygekko/api/demo/"


def _load(name):
    with open(DEMO + name, encoding="utf-8") as file:
        return json.load(file)


@pytest.mark.parametrize(
    ("entity_id", "state"),
    [
        ("binary_sensor.front_door_open", "off"),
        ("binary_sensor.garage_gate_open", "on"),
        ("binary_sensor.alarm_system_alarm", "off"),
        ("binary_sensor.alarm_system_zone_home_armed", "on"),
        ("binary_sensor.alarm_system_zone_garden_armed", "off"),
        ("binary_sensor.heat_pump_running", "on"),
        ("binary_sensor.wallbox_garage_plugged_in", "on"),
        ("binary_sensor.notifications_active", "on"),
        ("binary_sensor.living_room_audio_playing", "on"),
        ("sensor.heat_pump_flow_temperature", "35.5"),
        ("sensor.living_room_audio_volume", "35.0"),
        ("sensor.living_room_audio_title", "Demo song"),
        ("sensor.outdoor_outdoor_temperature", "12.5"),
        ("sensor.outdoor_humidity", "60.0"),
    ],
)
async def test_demo_states(hass, setup_demo, entity_id, state):
    """The read only device types are available in demo mode."""
    assert hass.states.get(entity_id).state == state


async def test_door_and_gate_device_classes(hass, setup_demo):
    """A gate is an opening, not a door."""
    assert hass.states.get("binary_sensor.front_door_open").attributes["device_class"] == "door"
    assert hass.states.get("binary_sensor.garage_gate_open").attributes["device_class"] == "opening"


async def test_unused_trend_variables_are_ignored(hass, setup_demo):
    """Only the variables that are in use become sensors."""
    trend_sensors = [
        state.entity_id
        for state in hass.states.async_all("sensor")
        if state.entity_id.startswith("sensor.outdoor_")
    ]
    assert sorted(trend_sensors) == [
        "sensor.outdoor_humidity",
        "sensor.outdoor_outdoor_temperature",
    ]
    assert (
        hass.states.get("sensor.outdoor_humidity").attributes["unit_of_measurement"] == "%"
    )


async def _setup_with(hass, change):
    resources = _load("api_var_demo_data.json")
    status = _load("api_var_status_demo_data.json")
    change(status)
    entry = MockConfigEntry(domain=DOMAIN, version=3, data=DEMO_CONFIG, unique_id="x")
    entry.add_to_hass(hass)
    with patch(
        "custom_components.mygekko.api.MyGekkoDemoModeClient._fetch_resources",
        return_value=resources,
    ), patch(
        "custom_components.mygekko.api.MyGekkoDemoModeClient._fetch_status",
        return_value=status,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_element_status_is_an_attribute(hass):
    """A locked or manually operated element is visible as attribute."""

    def lock_lights(status):
        for key, light in status["lights"].items():
            if not key.startswith("item"):
                continue
            fields = light["sumstate"]["value"].split(";")
            fields[4] = "3"
            light["sumstate"]["value"] = ";".join(fields)

    await _setup_with(hass, lock_lights)
    lights = [s for s in hass.states.async_all("light") if "element_status" in s.attributes]
    assert lights
    assert all(light.attributes["element_status"] == "locked" for light in lights)


async def test_ok_elements_have_no_status_attribute(hass, setup_demo):
    """Elements in normal operation do not clutter the attributes."""
    assert all(
        "element_status" not in state.attributes for state in hass.states.async_all("light")
    )


async def test_zone_alarm_counts_even_when_not_armed(hass):
    """An alarm of a zone that is not armed is an alarm as well."""

    def alarm(status):
        status["alarmsystem"]["item0"]["sumstate"]["value"] = "1;1;0;2;1;0;0;1"

    await _setup_with(hass, alarm)
    assert hass.states.get("binary_sensor.alarm_system_alarm").state == "on"
    assert hass.states.get("binary_sensor.alarm_system_zone_home_alarm").state == "on"
    assert hass.states.get("binary_sensor.alarm_system_zone_home_armed").state == "off"
