from enum import Enum

class PacketType(Enum):
    TYPE_HANDSHAKE = 0
    TYPE_DATA = 1
    TYPE_EOF = 2
    TYPE_ACK = 3
    TYPE_NAK = 4
    TYPE_TIMEOUT = 5
