import argparse
import struct
import time
import serial
import sys

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

        chunk_size = struct.unpack('>H', header_bytes)[0]
        
        data = ser.read(chunk_size)

        if len(data) < chunk_size:
            print("\nErro: Pacote incompleto recebido. Enviando NAK.")
            ser.write(b'NAK\n')
            return 'continue'

        if data == b'EOF':
            print("\nRecebido comando 'EOF'. Finalizando.")
            ser.write(b'ACK\n')
            return 'eof'

        file_handle.write(data)
        ser.write(b'ACK\n')
        return 'data' 

    except serial.SerialException as e:
        print(f"\nErro de comunicação serial: {e}")
        return 'error'
    except Exception as e:
        print(f"\nErro inesperado ao receber dado: {e}")
        return 'error'

def main():
    args = generate_arguments()
    ser = None
    
    try:
        ser = serial.Serial(args.com, args.velocity, timeout=2)
        print(f"Porta {args.com} aberta (Baud: {args.velocity}). Aguardando conexão...")
        
        while True:
            line = ser.readline()
            if line.strip() == b'hello':
                print("Recebido handshake 'hello', respondendo 'hello-back'")
                ser.write(b'hello-back\n')
                break
            time.sleep(0.1)
        
        print(f"Conexão estabelecida. Pronto para receber e salvar em '{args.output}'")
        
        bytes_received = 0
        with open(args.output, 'wb') as f:
            while True:
                status = listen_for_file_chunk(ser, f)
                
                if status == 'eof' or status == 'error':
                    break 
                
                if status == 'data':
                    bytes_received += 128
                    sys.stdout.write(f"\rRecebendo... {bytes_received} bytes")
                    sys.stdout.flush()

        print(f"\nTransferência concluída. Arquivo salvo em '{args.output}'.")

    except serial.SerialException as e:
        print(f"Erro ao abrir a porta serial '{args.com}': {e}")
    except IOError as e:
        print(f"Erro ao criar o arquivo '{args.output}': {e}")
    finally:
        if ser and ser.is_open:
            ser.close()
            print(f"Porta {args.com} fechada.")

if __name__ == "__main__":
    main()