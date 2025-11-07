import argparse
import os
import sys
import time
import serial

from model.packet_type import PacketType
from model.packet import Packet

STATE_AWAITING_HANDSHAKE = "AWAIT_HANDSHAKE"
STATE_RECEIVING_DATA = "AWAIT_DATA"

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
    
    state = STATE_AWAITING_HANDSHAKE
    
    timeout_inactivity = 10 
    timeout_counter = 0
    
    while True:
        try:
            print(f"Aguardando conexão na porta {args.com}...")
            ser = serial.Serial(args.com, args.baudrate, timeout=1.0)
            print(f"Porta {args.com} aberta.")
            
            state = STATE_AWAITING_HANDSHAKE
            timeout_counter = 0
            if file_writer:
                file_writer.close()
                file_writer = None
                
            while True:
                try:
                    status, packet = Packet.from_serial(ser)
                    
                    if status == 'EMPTY':
                        if state == STATE_RECEIVING_DATA:
                            send_response(ser, PacketType.TYPE_NAK)
                            timeout_counter += 1
                            print(f"Inatividade detectada... ({timeout_counter}/{timeout_inactivity})", end='\r')
                            
                            if timeout_counter >= timeout_inactivity:
                                print("\n[TIMER] Limite de inatividade. Descartando ficheiro e aguardando novo handshake.")
                                state = STATE_AWAITING_HANDSHAKE
                                timeout_counter = 0
                                if file_writer:
                                    file_writer.close()
                                    file_writer = None
                        continue
                    
                    if status == 'CORRUPTED':
                        print("\nPacote corrompido recebido. Enviando NAK.")
                        send_response(ser, PacketType.TYPE_NAK)
                        continue

                    timeout_counter = 0
                    
                    if packet.type == PacketType.TYPE_RESET_CONNECTION:
                        print("\n[RESET] Comando de reset recebido. Aguardando novo handshake.")
                        state = STATE_AWAITING_HANDSHAKE
                        if file_writer:
                            file_writer.close()
                            file_writer = None
                        continue

                    if state == STATE_AWAITING_HANDSHAKE:
                        if packet.type == PacketType.TYPE_HANDSHAKE:
                            print("Handshake recebido. Enviando resposta.")
                            send_response(ser, PacketType.TYPE_HANDSHAKE)
                            state = STATE_RECEIVING_DATA 
                        else:
                            print(f"Pacote {packet.type} ignorado, aguardando HANDSHAKE.")
                            send_response(ser, PacketType.TYPE_REQUEST_HANDSHAKE)

                    elif state == STATE_RECEIVING_DATA:
                        if packet.type == PacketType.TYPE_DATA:
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
                            print(f"Arquivo salvo: {output_filepath}. Aguardando novo handshake.")
                            state = STATE_AWAITING_HANDSHAKE 
                            
                        elif packet.type == PacketType.TYPE_HANDSHAKE:
                            print("Handshake recebido no meio da transferência. Ignorando.")
                            send_response(ser, PacketType.TYPE_WAITING_DATA)
                        
                        else:
                            print(f"Pacote {packet.type} inesperado. Enviando NAK.")
                            send_response(ser, PacketType.TYPE_NAK)
                except serial.SerialException as e:
                    print(f"\nErro de Hardware (read/write): {e}. Fechando porta.")
                    break 
        except serial.SerialException as e:
            print(f"\nErro ao abrir porta {args.com}: {e}")
            print("Tentando novamente em 3 segundos...")
        
        except KeyboardInterrupt:
            print("\nReceptor encerrado pelo usuário.")
            break 
        
        finally:
            if file_writer:
                file_writer.close()
                file_writer = None
            if ser and ser.is_open:
                ser.close()
            time.sleep(3)       
    

if __name__ == "__main__":
    main()