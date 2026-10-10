"""Constants for the Govee light local integration."""

from datetime import timedelta

DOMAIN = "govee_light_local"
MANUFACTURER = "Govee"

CONF_MULTICAST_ADDRESS_DEFAULT = "239.255.255.250"
CONF_TARGET_PORT_DEFAULT = 4001
CONF_LISTENING_PORT_DEFAULT = 4002
CONF_DISCOVERY_INTERVAL_DEFAULT = 60

SCAN_INTERVAL = timedelta(seconds=30)
# A device is considered unavailable if we have not heard a status response
# from it for three consecutive poll cycles. This tolerates a single dropped
# UDP response plus some jitter before flapping the entity state.
DEVICE_TIMEOUT = SCAN_INTERVAL * 3
DISCOVERY_TIMEOUT = 5

# --- Segment control (fork) -------------------------------------------------
SERVICE_SET_GRADIENT = "set_gradient"
ATTR_COLORS = "colors"
ATTR_REVERSE = "reverse"

# Dispatcher signal, formatted with the device fingerprint. Used by the main
# light to tell its segment entities that their colors changed.
SIGNAL_SEGMENTS_CHANGED = f"{DOMAIN}_segments_changed_{{}}"

# Small pause between consecutive segment commands so the device does not
# drop UDP datagrams that arrive back to back.
SEGMENT_SEND_DELAY = 0.05
# Dispatcher signal: the main light state changed (e.g. on/off).
SIGNAL_DEVICE_UPDATED = f"{DOMAIN}_device_updated_{{}}"

# Dispatcher signal: music sensitivity of a device changed.
SIGNAL_MUSIC_SENSITIVITY = f"{DOMAIN}_music_sensitivity_{{}}"
MUSIC_GROUP_DELAY = 0.15
