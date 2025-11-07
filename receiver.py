import argparse
import os
import sys
import time
import serial

from model.packet_type import PacketType
from model.packet import Packet

def generate_arguments():
    """Configura e analisa os argumentos da linha de comando."""
    parser = argparse.ArgumentParser(description="Receber arquivos via porta serial.")
    parser.add_argument("com", type=str, help="Nome da porta COM (ex: COM4 ou /dev/ttyUSB0).")
    parser.add_argument("-b", "--baudrate", type=int, default=9600,
                        help="Velocidade da porta COM (baud rate, ex: 9600).")
    parser.add_argument("-o", "--output", type=str, default="received_file.dat",
                        help="Nome do arquivo para salvar os dados (padrão: received_file.dat).")
    return parser.parse_args()

def send_response(ser, type: PacketType):
    response_packet = Packet(type, "")
    ser.write(response_packet.get_full_packet_bytes())

def main():
    args = generate_arguments()
    output_filepath = args.output
    ser = None
    file_writer = None
    new_connection = True
    
    timeout_inactivity = 10 
    timeout_counter = 0
        
    print(f"Aguardando conexões em {args.com} a {args.baudrate} baud...")
    try:
        ser = serial.Serial(args.com, args.baudrate, timeout=1.0) 
        while True:
            try:
                packet = Packet.from_serial(ser)
                if not packet:
                    if not new_connection:
                        timeout_counter += 1
                        print(f"Inatividade detectada... ({timeout_counter}/{timeout_inactivity})", end='\r')
                        
                        if timeout_counter >= timeout_inactivity:
                            print("\n[TIMER] Limite de inatividade atingido. Resetando estado da conexão.")
                            new_connection = True 
                            timeout_counter = 0   
                            
                            if file_writer:
                                file_writer.close()
                                file_writer = None
                                print("[TIMER] Ficheiro parcial descartado.")  
                                    
                    ser.reset_input_buffer()              
                    continue
                
                timeout_counter = 0
                
                if packet.type == PacketType.TYPE_HANDSHAKE:                    
                    if not new_connection:
                        send_response(ser, PacketType.TYPE_WAITING_DATA)
                        continue
                    print("Handshake recebido. Enviando resposta...")
                    send_response(ser, PacketType.TYPE_HANDSHAKE)                    
                elif packet.type == PacketType.TYPE_DATA:
                    if new_connection:
                        send_response(ser, PacketType.TYPE_REQUEST_HANDSHAKE)
                        continue
                    new_connection = False
                    if file_writer is None:
                        file_writer = open(output_filepath, 'wb')
                    file_writer.write(packet.data)
                    print(f"Recebido chunk de {len(packet.data)} bytes.", end='\r')
                    send_response(ser, PacketType.TYPE_ACK)
                elif packet.type == PacketType.TYPE_EOF:
                    print("\nSinal de EOF recebido. Finalizando...")
                    if file_writer:
                        file_writer.close()
                        file_writer = None
                    send_response(ser, PacketType.TYPE_ACK)
                    print(f"Arquivo salvo com sucesso em {output_filepath}. Reiniciando...")
                    new_connection = True
                elif packet.type == PacketType.TYPE_RESET_CONNECTION:
                    print("Resetando conexão...")
                    new_connection = True
                    continue
                else:
                    print(f"Pacote de tipo inesperado recebido: {packet.type}")
                    send_response(ser, PacketType.TYPE_NAK)
            except serial.SerialException as e:
                print(f"Erro de hardware: {e}. Tentando reabrir porta...")
                if ser and ser.is_open:
                    ser.close()
                time.sleep(2)
                ser = serial.Serial(args.com, args.baudrate, timeout=1.0)
            except Exception as e:
                print(f"Erro inesperado no loop: {e}")
    except KeyboardInterrupt:
        print("\nReceptor encerrado pelo usuário.")
    except serial.SerialException as e:
        print(f"Erro fatal: Não foi possível abrir a porta {args.com}. {e}")
        sys.exit(1)
    finally:
        if file_writer:
            file_writer.close()
            
        if ser and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()