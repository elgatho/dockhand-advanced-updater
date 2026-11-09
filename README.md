# Dockhand Advanced Updater

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant integration that adds **scheduled, presence-aware auto-updates** for the containers managed by [Dockhand](https://dockhand.pro). 🇵🇱 [Polska wersja](README.pl.md)

## Features

- Lists all containers from every (or selected) Dockhand environment.
- **Exclude** containers from auto-update; excluded containers get a manual **Update** button.
- Auto-update at a chosen **time** on chosen **days of the week**: every non-excluded container with an available image update is updated.
- Optional **"only when someone is home"** with a choice of `person` entities. If nobody is home at the scheduled time, the run is deferred and starts when a selected person arrives (same day).
- Respects Dockhand's *minimum release age* (containers still in the waiting period are skipped).
- Entities: per-container *update available* binary sensor, *Pending updates*, *Next auto-update*, *Last update run* sensors, an *Auto-update* master switch, *Check for updates* and *Force auto-update* buttons (runs the auto-update immediately for non-excluded containers only; excluded ones are never touched).
- Event `dockhand_advanced_updater_run_finished` (`reason`, `updated`, `failed`, `finished`) – use it for notifications.
- Full UI configuration (config flow, options flow, re-auth) in English and Polish.
- Pressing a button shows a persistent notification (started / finished with result); repeated presses while a run is in progress are rejected.

## Example dashboard

A ready-to-paste card with status, pending updates and manual-update buttons is in [`examples/dashboard.yaml`](examples/dashboard.yaml). It needs the [auto-entities](https://github.com/thomasloven/lovelace-auto-entities) card; the two lists fill themselves, only the five status entity IDs at the top need to match yours.

## Installation

### HACS (custom repository)
1. HACS → ⋮ → *Custom repositories* → add this repository, category **Integration**.
2. Install **Dockhand Advanced Updater** and restart Home Assistant.

### Manual
Copy `custom_components/dockhand_advanced_updater` into your HA `config/custom_components/` and restart.

## Setup

1. *Settings → Devices & services → Add integration → Dockhand Advanced Updater*.
2. Enter the Dockhand URL and an **API token** (Dockhand profile → API tokens; the token needs permission to list and recreate containers). Leave the token empty only if Dockhand authentication is disabled.
3. Click **Configure** on the integration to set:
   - environments, update time, days, "only when home" + people, refresh interval,
   - then the list of containers **excluded** from auto-update.

Changing options reloads the integration. Buttons are created only for excluded containers.

## How updates work

Updates use Dockhand's batch-update endpoint, which re-pulls the image and recreates the container keeping its configuration. Containers are identified by `environment id : name` because Docker IDs change after every update.

## Notes

- Updates are performed by Dockhand; Home Assistant only triggers them. Update the container running Home Assistant itself manually.
- Requires Home Assistant 2024.11 or newer.

## License
MIT
