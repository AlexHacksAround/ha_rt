"""Constants for the Service Management integration."""

DOMAIN = "ha_rt"

# RT API constants - Ticket fields
DEVICE_ID_FIELD = "DeviceId"
DEVICE_INFO_FIELD = "Device Information"
AREA_FIELD = "Area"
ADDRESS_FIELD = "Address"
OPEN_STATUSES = ["new", "open", "stalled"]

# RT API constants - Asset fields
ASSET_MANUFACTURER_FIELD = "Manufacturer"
ASSET_MODEL_FIELD = "Model"
ASSET_SERIAL_FIELD = "Serial Number"
ASSET_FIRMWARE_FIELD = "Firmware Version"
ASSET_HARDWARE_FIELD = "Hardware Version"
ASSET_CONFIG_URL_FIELD = "Configuration URL"
ASSET_MAC_FIELD = "MAC Address"

# Config keys
CONF_URL = "url"
CONF_TOKEN = "token"
CONF_QUEUE = "queue"
CONF_HA_URL = "ha_url"
CONF_ADDRESS = "address"
CONF_CATALOG = "catalog"
CONF_SYNC_INTERVAL = "sync_interval"

# Defaults
DEFAULT_QUEUE = "Facility Management"
DEFAULT_CATALOG = "HA Murten"
DEFAULT_SYNC_INTERVAL = 6  # hours

# Services
SERVICE_SYNC_ASSETS = "sync_assets"
