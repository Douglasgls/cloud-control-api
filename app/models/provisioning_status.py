from enum import Enum


class ProvisioningStatus(str, Enum):
    PENDING = "PENDING"
    USER_READY = "USER_READY"
    KEY_CREATED = "KEY_CREATED"
    WAITING_AGENT = "WAITING_AGENT"
    CONNECTED = "CONNECTED"
