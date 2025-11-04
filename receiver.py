import argparse
import struct
import time
import zlib
import serial

CRC_SIZE = 4 

def generate_arguments():
    """Configura e analisa os argumentos da linha de comando."""
    parser = argparse.ArgumentParser(description="Receber arquivos via porta serial.")
    parser.add_argument("com", type=str, help="Nome da porta COM (ex: COM4 ou /dev/ttyUSB0).")
    parser.add_argument("velocity", type=int, help="Velocidade da porta COM (baud rate, ex: 9600).")
    parser.add_argument("-o", "--output", type=str, default="received_file.dat",
                        help="Nome do arquivo para salvar os dados (padrão: received_file.dat).")
    return parser.parse_args()

def listen_for_file_chunk(ser, file_handle):
    try:
        header_bytes = ser.read(2)
        if len(header_bytes) < 2:
            return 'continue' 

        payload_size = struct.unpack('>H', header_bytes)[0]
        payload = ser.read(payload_size)

        if len(payload) < payload_size:
            print("\nErro: Pacote incompleto recebido. Enviando NAK.")
            ser.write(b'NAK\n')
            return 'continue'
        
        data = payload[:-CRC_SIZE]           
        crc_received_bytes = payload[-CRC_SIZE:]

        try:
            crc_received = struct.unpack('>I', crc_received_bytes)[0]
            crc_calculated = zlib.crc32(data)
        except Exception as e:
            print(f"\nErro ao desempacotar CRC (pacote malformado): {e}. Enviando NAK.")
            ser.write(b'NAK\n')
            return 'continue'
        
        if crc_calculated != crc_received:
            print(f"\nErro: Falha na verificação do CRC. (Recebido: {crc_received}, Calculado: {crc_calculated}). Enviando NAK.")
            ser.write(b'NAK\n')
            return 'continue'
        
        if data == b'EOF':
            print("\nRecebido comando 'EOF'. Finalizando.")
            ser.write(b'ACK\n')
            return 'eof'

        file_handle.write(data)
        ser.write(b'ACK\n')
        return 'data'     
    except Exception as e:
        print(f"\nErro inesperado ao receber dado: {e}")
        return 'error'

            
def main():
    args = generate_arguments()
    ser = None
    
    while True:
        try:
            print(f"Tentando conectar na porta {args.com}...")
            ser = serial.Serial(args.com, args.velocity, timeout=2)
            print(f"Porta {args.com} aberta com sucesso. Aguardando dados...")
            
            while True:
                line = ser.readline()
                if line.strip() == b'hello':
                    print("Recebido handshake 'hello', respondendo 'hello-back'")
                    ser.write(b'hello-back\n')
                    break 
                
                time.sleep(0.1)
            
            print(f"Conexão estabelecida. Pronto para receber e salvar em '{args.output}'")

            with open(args.output, 'wb') as f:
                while True:
                    status = listen_for_file_chunk(ser, f)
                    
                    if status == 'eof' or status == 'error':
                        break 
            
            print(f"\nTransferência concluída. Arquivo salvo em '{args.output}'.")
            break 

        except serial.SerialException as e:
            print(f"\nErro de comunicação serial: {e}")
            print("Dispositivo desconectado ou porta indisponível. Tentando reconectar em 5 segundos...")
            if ser and ser.is_open:
                ser.close()
            time.sleep(5) 
            
        except IOError as e:
            print(f"Erro ao criar o arquivo '{args.output}': {e}")
            break
        
        except Exception as e:
            print(f"Erro inesperado no loop principal: {e}")
            if ser and ser.is_open:
                ser.close()
            time.sleep(5)

    print("Programa finalizado.")
    if ser and ser.is_open:
        ser.close()            

if __name__ == "__main__":
    main()