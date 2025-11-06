from enum import Enum

class PacketType(Enum):
    TYPE_HANDSHAKE = 3
    TYPE_PARAMS = 0
    TYPE_DATA = 1
    TYPE_EOF = 2
    TYPE_ACK = 4
    TYPE_NAK = 5
    TYPE_TIMEOUT = 6
