import argparse
import os
import sys
import time

import serial

from model.connection_params import ConnectionParams
from model.packet_type import PacketType
from model.packet import Packet

def generate_arguments():
    parser = argparse.ArgumentParser(description="Enviar arquivos utilizando porta serial.")
    parser.add_argument("com", type=str, help="Nome da porta COM (ex: COM4 ou /dev/ttyUSB0).")
    parser.add_argument("-b", "--baudrate", type=int, default=9600,
                        help="Velocidade da porta COM (baud rate, ex: 9600).")
    parser.add_argument("path", type=str, help="Localização do arquivo a ser transferido.")
    return parser.parse_args()

def wait_for_packet(ser, expected_type):
    try:
        packet = Packet.from_serial(ser)
        if packet:
            if packet.type == expected_type:
                return 'ACK' 
            if packet.type == PacketType.TYPE_NAK:
                return 'NAK'
        
        return 'TIMEOUT'
    except Exception as e:
        print(f"\nErro ao aguardar pacote: {e}")
        return 'TIMEOUT'

def perform_handshake(ser, max_retries):
    print("Iniciando handshake...")
    packet = Packet(PacketType.TYPE_HANDSHAKE, "")
    ser.reset_input_buffer() 
    
    for attempt in range(max_retries):
        print(f"Tentativa de handshake [{attempt + 1}/{max_retries}]...")
        try: 
            ser.write(packet.get_full_packet_bytes())
            
            response = wait_for_packet(ser, PacketType.TYPE_HANDSHAKE)
            
            if response == 'ACK': 
                print("Handshake bem-sucedido! O receptor está pronto.")
                return True
            else:
                print(f"Resposta não recebida ou incorreta.")
                
            if attempt < max_retries - 1:
                time.sleep(1.0)
                
        except serial.SerialException as e:
            print(f"Erro de hardware na tentativa: {e}")
            time.sleep(1.0)
    
    print("Falha no handshake após todas as tentativas.")
    return False

def send_connection_params(ser, params):
    packet = Packet(PacketType.TYPE_PARAMS, params)
    
    for attempt in range(params.max_retries):
        print(f"Enviando parâmetros da conexão, tentativa [{attempt + 1}/{params.max_retries}]...")
        ser.write(packet.get_full_packet_bytes())
        
        response = wait_for_packet(ser, PacketType.TYPE_ACK)
            
        if response == 'ACK':
            print(f"Parâmetros enviados e confirmados.")
            return True
        elif response == 'NAK':
            print(f"\nReceptor reportou erro (NAK). Retentando...")
        else: 
            print(f"\nSem resposta do receptor (timeout). Retentando...")
    
    print("Falha no envio dos parâmetros após todas as tentativas.")
    return False

def send_file_in_chunks(ser, filepath, data_size, max_retries):
    if not os.path.exists(filepath):
        print(f"Erro: Arquivo '{filepath}' não encontrado.")
        return False

    file_size = os.path.getsize(filepath)
    print(f"Iniciando envio do arquivo '{filepath}' ({file_size} bytes)...")

    with open(filepath, 'rb') as f:
        bytes_sent = 0
        
        while True:
            payload_data = f.read(data_size)
            if not payload_data:
                break 

            packet = Packet(PacketType.TYPE_DATA, payload_data)
            retries = 0
            ack_received = False
            
            while not ack_received and retries < max_retries:
                ser.write(packet.get_full_packet_bytes())
                
                response = wait_for_packet(ser, PacketType.TYPE_ACK)
                    
                if response == 'ACK':
                    ack_received = True
                    bytes_sent += len(payload_data)
                elif response == 'NAK':
                    print(f"\nReceptor reportou erro (NAK). Retentando chunk... ({retries + 1})")
                    retries += 1
                else: 
                    print(f"\nSem resposta do receptor (timeout). Retentando... ({retries + 1})")
                    retries += 1

                progress = (bytes_sent / file_size) * 100
                print(f"Enviando... {bytes_sent}/{file_size} bytes ({progress:.2f}%)", end='\r')
            
            if not ack_received:
                print(f"\nFalha ao enviar chunk após {max_retries} tentativas. Abortando.")
                return False

    print("\nArquivo enviado. Enviando sinal de EOF...")
    eof_packet = Packet(PacketType.TYPE_EOF, "")
    
    retries = 0
    eof_acked = False
        
    while not eof_acked and retries < max_retries:
        ser.write(eof_packet.get_full_packet_bytes())
        response = wait_for_packet(ser, PacketType.TYPE_ACK)
        
        if response == 'ACK':
            eof_acked = True
        else:
            print(f"Receptor não confirmou EOF. Retentando... ({retries + 1})")
            retries += 1
    
    if eof_acked:
        print("Transferência concluída com sucesso!")
        return True
    else:
        print("Falha ao finalizar a transferência. O receptor pode estar offline.")
        return False
    
def main():
    args = generate_arguments()
    
    if not os.path.exists(args.path):
        print(f"Erro: O arquivo '{args.path}' não foi encontrado.")
        sys.exit(1)
    
    ser = None
    
    params = ConnectionParams(
        timeout = 90, 
        max_retries = 90,
        data_size = 60, 
    ) 
            
    ser = serial.Serial(args.com, args.baudrate, timeout=1.0)
    while(True):
        try:           
            print(f"Tentando conectar na porta {args.com}...")
            if ser and ser.is_open:
                ser.close()
            
            ser = serial.Serial(args.com, args.baudrate, timeout=2.0)
            ser.timeout = params.timeout
            
            if not perform_handshake(ser, params.max_retries):
                print("Handshake falhou, retentando conexão...")
                time.sleep(2)
                continue
            
            if not send_connection_params(ser, params):
                print("Envio de parâmetros falhou, retentando conexão...")
                time.sleep(2)
                continue
                                
            if not send_file_in_chunks(ser, args.path, params.data_size, params.max_retries):
                print("Falha ao enviar arquivo (timeout), retentando conexão...")
                time.sleep(2)
                continue   
            
            print("Arquivo enviado com sucesso!")           
            break
            
        except serial.SerialException as e:
            print(f"Erro de hardware (porta removida?): {e}")
            print(f"Tentando reconectar em 2 segundos...")
            time.sleep(2)
        
        except KeyboardInterrupt:
            print("\nEnvio cancelado pelo usuário.")
            break
           
    if ser and ser.is_open:
        ser.close()
if __name__ == "__main__":
    main()