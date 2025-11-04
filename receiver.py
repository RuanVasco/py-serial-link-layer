import argparse
import struct
import time
import zlib
import serial
import json

TYPE_PARAMS = 0
TYPE_DATA = 1
TYPE_EOF = 2

CONN_PARAMS = {
    "data_size": 60,      
    "crc_size": 4,
    "max_retries": 3,
    "timeout": 5
}

MAX_INACTIVITY_TIMEOUTS = 5 

def generate_arguments():
    """Configura e analisa os argumentos da linha de comando."""
    parser = argparse.ArgumentParser(description="Receber arquivos via porta serial.")
    parser.add_argument("com", type=str, help="Nome da porta COM (ex: COM4 ou /dev/ttyUSB0).")
    parser.add_argument("velocity", type=int, help="Velocidade da porta COM (baud rate, ex: 9600).")
    parser.add_argument("-o", "--output", type=str, default="received_file.dat",
                        help="Nome do arquivo para salvar os dados (padrão: received_file.dat).")
    return parser.parse_args()

def process_packet(ser):
    """
    Lê e valida um pacote completo (tipo, tamanho, payload, crc).
    Retorna (packet_type, payload_data) em caso de sucesso.
    Retorna ('TIMEOUT', None) em caso de inatividade.
    Retorna ('ERROR', None) em caso de erro de pacote.
    """
    global CONN_PARAMS
    CRC_SIZE = CONN_PARAMS["crc_size"]
    
    try:
        type_header_bytes = ser.read(2)
        if len(type_header_bytes) < 2:
            return 'TIMEOUT', None 

        length_header_bytes = ser.read(2)
        if len(length_header_bytes) < 2:
            print("\nErro: Pacote malformado (faltou header de tamanho).")
            return 'ERROR', None 

        packet_type = struct.unpack('>H', type_header_bytes)[0]
        payload_length = struct.unpack('>H', length_header_bytes)[0]

        payload_data = ser.read(payload_length)
        if len(payload_data) < payload_length:
            print("\nErro: Pacote incompleto (payload).")
            return 'ERROR', None
        
        crc_bytes = ser.read(CRC_SIZE)
        if len(crc_bytes) < CRC_SIZE:
            print("\nErro: Pacote incompleto (CRC).")
            return 'ERROR', None

        crc_received = struct.unpack('>I', crc_bytes)[0]
        crc_calculated = zlib.crc32(payload_data)
        
        if crc_calculated != crc_received:
            print(f"\nErro: Falha no CRC. (Recebido: {crc_received}, Calculado: {crc_calculated}).")
            return 'ERROR', None
        
        return packet_type, payload_data

    except Exception as e:
        print(f"\nErro crítico ao processar pacote: {e}")
        return 'ERROR', None


def main():
    global CONN_PARAMS
    
    args = generate_arguments()
    ser = None
    newConnection = True
    
    while True:
        try:
            print(f"Tentando conectar na porta {args.com}...")
            if ser and ser.is_open:
                ser.close()
            
            ser = serial.Serial(args.com, args.velocity, timeout=2) 
            print(f"Porta {args.com} aberta. Aguardando handshake 'hello'...")
            
            while True: 
                if (newConnection):
                    line = ser.readline()
                    if line.strip() == b'hello':
                        print("Recebido handshake 'hello', respondendo 'hello-back'")
                        ser.write(b'hello-back\n')
                    else:
                        continue
                    
                    print("Aguardando parâmetros de conexão...")
                    
                    ser.timeout = CONN_PARAMS["timeout"] 
                
                packet_type, payload_data = process_packet(ser)
                
                if packet_type == TYPE_PARAMS:
                    try:
                        params = json.loads(payload_data.decode('utf-8'))
                        CONN_PARAMS.update(params) 
                        ser.timeout = CONN_PARAMS["timeout"] 
                        print(f"Parâmetros recebidos e aplicados: {CONN_PARAMS}")
                        ser.write(b'ACK\n')
                    except Exception as e:
                        print(f"Erro ao decodificar parâmetros: {e}")
                        ser.write(b'NAK\n')
                        continue
                elif packet_type == 'TIMEOUT':
                    print("Timeout esperando parâmetros.")
                    continue
                else:
                    print("Erro: Esperava parâmetros, recebi outro pacote.")
                    ser.write(b'NAK\n')
                    continue 

                print(f"Pronto para receber e salvar em '{args.output}'")
                timeout_counter = 0
                
                try:
                    with open(args.output, 'wb') as f:
                        while True:
                            packet_type, payload_data = process_packet(ser)

                            if packet_type == TYPE_DATA:
                                timeout_counter = 0
                                f.write(payload_data)
                                ser.write(b'ACK\n')
                                
                            elif packet_type == TYPE_EOF:
                                print(f"\nTransferência concluída. Arquivo salvo em '{args.output}'.")
                                ser.write(b'ACK\n')
                                break
                                
                            elif packet_type == 'TIMEOUT':
                                timeout_counter += 1
                                print(f"Aguardando dados... (Timeout {timeout_counter}/{MAX_INACTIVITY_TIMEOUTS})", end='\r')
                                if timeout_counter >= MAX_INACTIVITY_TIMEOUTS:
                                    print(f"\nLimite de inatividade atingido. Resetando conexão.")
                                    break 
                                    
                            else: 
                                print(f"\nPacote inesperado (tipo {packet_type}) ou erro. Enviando NAK.")
                                ser.write(b'NAK\n')
                                
                except IOError as e:
                    print(f"Erro ao escrever o arquivo '{args.output}': {e}")
                
                print("\nVoltando a aguardar por handshake...")

        except serial.SerialException as e:
            print(f"\nErro de comunicação serial: {e}")
            print("Dispositivo desconectado ou porta indisponível. Tentando reconectar em 5 segundos...")
            if newConnection:
                newConnection = False
            if ser and ser.is_open:
                ser.close()
            time.sleep(5) 
            
        except KeyboardInterrupt:
            print("\nOperação cancelada pelo usuário. Finalizando...")
            break
            
        except Exception as e:
            print(f"Erro inesperado no loop principal: {e}")
            if ser and ser.is_open:
                ser.close()
            print("Tentando reconectar em 5 segundos...")
            time.sleep(5)

    print("Programa finalizado.")
    if ser and ser.is_open:
        ser.close()

if __name__ == "__main__":
    main()
