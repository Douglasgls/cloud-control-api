from enum import Enum


class ConnectionStatus(str, Enum):
    PENDING = "PENDING"
    CONNECTED = "CONNECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    DISCONNECTED = "DISCONNECTED"

