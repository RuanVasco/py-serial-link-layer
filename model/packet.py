import base64
import json
import struct
import zlib

import serial

from model.connection_params import ConnectionParams
from model.packet_type import PacketType
       
class Packet():
    def __init__(self, type: PacketType, data):
        self.type_val = type 
        self.type = struct.pack('>H', type.value)
        
        payload_data = self._serialize_data(type, data)
        
        self.data = payload_data.encode('utf-8')
        self.length = struct.pack('>H', len(self.data))
        self.crc_bytes = struct.pack('>I', zlib.crc32(self.data))
        
    def _serialize_data(self, type, data):
        if type == PacketType.TYPE_DATA and isinstance(data, bytes):
            data_to_serialize = base64.b64encode(data).decode('utf-8')
        else:
            data_to_serialize = data
            
        return json.dumps(data_to_serialize)
    
    def get_full_packet_bytes(self):
        return self.type + self.length + self.data + self.crc_bytes
        
    def validate(self):
        if self.data is None or self.crc_bytes is None:
            return False
            
        crc_calculated = zlib.crc32(self.data)
        
        try:
            crc_received = struct.unpack('>I', self.crc_bytes)[0]
        except (struct.error, TypeError):
            return False

        return crc_calculated == crc_received
    
    @classmethod
    def from_serial(cls, ser):
        CRC_SIZE = 4 
        
        try:
            type_header_bytes = ser.read(2)
            length_header_bytes = ser.read(2)
            if len(type_header_bytes) < 2 or len(length_header_bytes) < 2:
                return None 

            packet_type_val = struct.unpack('>H', type_header_bytes)[0]
            payload_length = struct.unpack('>H', length_header_bytes)[0]

            payload_data = ser.read(payload_length)
            crc_bytes = ser.read(CRC_SIZE)
            if len(payload_data) < payload_length or len(crc_bytes) < CRC_SIZE:
                print("\nErro: Pacote incompleto (payload/crc).")
                return None 

            packet = cls.__new__(cls)
            packet.type_bytes = type_header_bytes
            packet.length_bytes = length_header_bytes
            packet.data = payload_data 
            packet.crc_bytes = crc_bytes
            
            if not packet.validate():
                print(f"\nErro: Falha no CRC para pacote tipo {packet_type_val}.")
                return None
            
            packet.type = PacketType(packet_type_val)
            
            try:
                decoded_payload = json.loads(packet.data.decode('utf-8'))
            except json.JSONDecodeError:
                print(f"\nErro: Falha ao decodificar JSON do payload.")
                return None

            if packet.type == PacketType.TYPE_DATA:
                packet.data = base64.b64decode(decoded_payload)            
            else:
                packet.data = decoded_payload
                
            return packet
            
        except serial.SerialException as e:
            print(f"Erro de serial em from_serial: {e}")
            return None
        except Exception as e:
            print(f"Erro inesperado em from_serial: {e}")
            return None