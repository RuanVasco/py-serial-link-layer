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
                ser.reset_input_buffer()
                return None 
            packet_type_val = struct.unpack('>H', type_header_bytes)[0]
            payload_length = struct.unpack('>H', length_header_bytes)[0]
            
            try:
                packet_type = PacketType(packet_type_val)
            except ValueError:
                ser.reset_input_buffer()
                print(f"\nErro: Tipo de pacote desconhecido: {packet_type_val}")
                return None

            payload_data = ser.read(payload_length)
            if len(payload_data) < payload_length:
                print("\nErro: Pacote incompleto (payload).")
                ser.reset_input_buffer()
                return None 

            packet = cls.__new__(cls)
            packet.type = packet_type
            packet.type_bytes = type_header_bytes
            packet.length_bytes = length_header_bytes
            packet.data = payload_data 
            
            if packet.type not in (PacketType.TYPE_HANDSHAKE, PacketType.TYPE_ACK, PacketType.TYPE_NAK):
                
                crc_bytes = ser.read(CRC_SIZE)
                if len(crc_bytes) < CRC_SIZE:
                    ser.reset_input_buffer()
                    print("\nErro: Pacote incompleto (CRC).")
                    return None
                
                packet.crc_bytes = crc_bytes
                
                if not packet.validate():
                    ser.reset_input_buffer()
                    print(f"\nErro: Falha no CRC para pacote tipo {packet.type.name}.")
                    return None

            if packet.type == PacketType.TYPE_PARAMS:
                try:
                    decoded_payload = json.loads(packet.data.decode('utf-8'))
                    
                    packet.data = ConnectionParams(**decoded_payload) 
                    
                except Exception as e:
                    print(f"\nErro: Falha ao decodificar JSON/Params do payload: {e}")
                    ser.reset_input_buffer()
                    return None
                
            return packet
            
        except serial.SerialException as e:
            print(f"Erro de serial em from_serial: {e}")
            raise e 
        except Exception as e:
            print(f"Erro inesperado em from_serial: {e}")
            return None