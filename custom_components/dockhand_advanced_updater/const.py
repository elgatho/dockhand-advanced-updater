"""Constants for the Dockhand Advanced Updater integration."""

from __future__ import annotations

import logging

DOMAIN = "dockhand_advanced_updater"
LOGGER = logging.getLogger(__package__)

# Config entry data
CONF_URL = "url"
CONF_TOKEN = "token"
CONF_VERIFY_SSL = "verify_ssl"

# Options
CONF_ENVIRONMENTS = "environments"
CONF_EXCLUDED = "excluded"
CONF_UPDATE_TIME = "update_time"
CONF_UPDATE_DAYS = "update_days"
CONF_ONLY_HOME = "only_when_home"
CONF_PERSONS = "persons"
CONF_CHECK_BEFORE = "check_before_update"
CONF_SCAN_INTERVAL = "scan_interval"

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # index == date.weekday()

DEFAULT_OPTIONS: dict = {
    CONF_ENVIRONMENTS: [],  # empty list == all environments
    CONF_EXCLUDED: [],  # list of "<env_id>:<container name>"
    CONF_UPDATE_TIME: "03:00:00",
    CONF_UPDATE_DAYS: ["sun"],
    CONF_ONLY_HOME: False,
    CONF_PERSONS: [],
    CONF_CHECK_BEFORE: True,
    CONF_SCAN_INTERVAL: 15,
}

EVENT_RUN_FINISHED = f"{DOMAIN}_run_finished"

# Timeouts (seconds). Pulling images and recreating containers can take a while.
TIMEOUT_DEFAULT = 30
TIMEOUT_CHECK = 600
TIMEOUT_UPDATE = 1800


def container_key(env_id: int, name: str) -> str:
    """Stable identifier of a container (its Docker ID changes on every update)."""
    return f"{env_id}:{name}"
