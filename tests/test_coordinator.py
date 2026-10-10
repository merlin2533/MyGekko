"""Tests for the polling behavior of the coordinator."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mygekko import coordinator as coordinator_module
from custom_components.mygekko.api import MyGekkoTooManyRequests
from custom_components.mygekko.const import DOMAIN

from .const import DEMO_CONFIG

READ_DATA = "custom_components.mygekko.api.MyGekkoDemoModeClient.read_data"


async def test_rate_limit_skips_polls_and_keeps_entities_available(hass, setup_demo):
    """HTTP 429 skips the poll, the entities keep their values."""
    coordinator = setup_demo.runtime_data
    light = hass.states.get("light.kitchen")
    assert light.state == "on"

    with patch(READ_DATA, side_effect=MyGekkoTooManyRequests("429")):
        for skipped in range(1, coordinator_module.MAX_SKIPPED_POLLS + 1):
            coordinator._backoff_until = 0
            await coordinator.async_refresh()
            assert coordinator.last_update_success
            assert hass.states.get("light.kitchen").state == "on"
            assert coordinator._skipped_polls == skipped

        # the interval grows, but never beyond the maximum
        assert coordinator.update_interval == coordinator_module.MAX_BACKOFF_INTERVAL

        # the rate limit persists: now the problem becomes visible
        coordinator._backoff_until = 0
        await coordinator.async_refresh()
        assert not coordinator.last_update_success


async def test_refresh_is_dropped_during_backoff(hass, setup_demo):
    """No request is sent while the rate limit backoff is active."""
    coordinator = setup_demo.runtime_data
    with patch(READ_DATA, side_effect=MyGekkoTooManyRequests("429")) as read_data:
        await coordinator.async_refresh()
        calls = read_data.call_count
        await coordinator.async_refresh()
        await coordinator.async_refresh()
    assert read_data.call_count == calls


async def test_recovery_restores_the_interval(hass, setup_demo):
    """After a successful poll the normal interval is back."""
    coordinator = setup_demo.runtime_data
    with patch(READ_DATA, side_effect=MyGekkoTooManyRequests("429")):
        await coordinator.async_refresh()
    assert coordinator.update_interval > coordinator.base_interval

    coordinator._backoff_until = 0
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.update_interval == coordinator.base_interval
    assert coordinator._skipped_polls == 0
    assert coordinator.update_interval == timedelta(seconds=30)


async def test_errors_become_update_failed_with_message(hass, setup_demo):
    """Other errors mark the update as failed with a readable message."""
    coordinator = setup_demo.runtime_data
    with patch(READ_DATA, side_effect=TimeoutError):
        await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert "Timeout" in str(coordinator.last_exception)


async def test_persistent_rate_limit_creates_a_repair_issue(hass, setup_demo):
    """A rate limit that does not go away is reported, and cleared on recovery."""
    coordinator = setup_demo.runtime_data
    registry = ir.async_get(hass)
    issue_id = f"rate_limited_{setup_demo.entry_id}"

    with patch(READ_DATA, side_effect=MyGekkoTooManyRequests("429")):
        for _ in range(coordinator_module.MAX_SKIPPED_POLLS):
            coordinator._backoff_until = 0
            await coordinator.async_refresh()
        assert registry.async_get_issue(DOMAIN, issue_id) is None

        coordinator._backoff_until = 0
        await coordinator.async_refresh()
    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "rate_limited"

    coordinator._backoff_until = 0
    await coordinator.async_refresh()
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_configured_interval_is_the_base_interval(hass):
    """The poll interval of the options is used."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        data=DEMO_CONFIG,
        options={"scan_interval": 120},
        unique_id="demo-interval",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval == timedelta(seconds=120)
