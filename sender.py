import sys
import serial
import os
import struct  
import argparse

TIMEOUT = 5  
CHUNK_SIZE = 64  
MAX_RETRIES = 3  

def perform_handshake(ser):
    try:
        print("Iniciando handshake... (Pressione Ctrl+C para cancelar)")
        ser.reset_input_buffer() 
        ser.write(b'hello\n')
        response = ser.readline().strip()

        if response == b'hello-back':
            print("Handshake bem-sucedido! O receptor está pronto.")
            return True
        else:
            print(f"Falha no handshake. Resposta recebida: '{response.decode(errors='ignore')}'")
            return False
            
    except Exception as e:
        print(f"Erro durante o handshake: {e}")
        return False

def wait_for_ack(ser):
    try:
        response = ser.readline().strip()
        if response == b'ACK':
            return 'ACK'
        if response == b'NAK':
            print("Recebeu NAK")
            return 'NAK'
        return 'TIMEOUT'
    except Exception as e:
        print(f"\nErro ao aguardar ACK: {e}")
        return 'TIMEOUT'

def send_file_in_chunks(ser, filepath):
    if not os.path.exists(filepath):
        print(f"Erro: Arquivo '{filepath}' não encontrado.")
        return False

    file_size = os.path.getsize(filepath)
    print(f"Iniciando envio do arquivo '{filepath}' ({file_size} bytes)...")

    try:
        with open(filepath, 'rb') as f:
            bytes_sent = 0
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break  
                
                header = struct.pack('>H', len(chunk))
                
                retries = 0
                ack_received = False
                
                while not ack_received and retries < MAX_RETRIES:
                    ser.write(header + chunk)
                    
                    response = wait_for_ack(ser)
                    
                    if response == 'ACK':
                        ack_received = True
                        bytes_sent += len(chunk)
                    elif response == 'NAK':
                        print(f"\nReceptor reportou erro (NAK). Retentando chunk... ({retries + 1})")
                        retries += 1
                    else: 
                        print(f"\nSem resposta do receptor (timeout). Retentando... ({retries + 1})")
                        retries += 1
                
                if not ack_received:
                    print(f"\nFalha ao enviar chunk após {MAX_RETRIES} tentativas. Abortando.")
                    return False 

                progress = (bytes_sent / file_size) * 100
                print(f"Enviando... {bytes_sent}/{file_size} bytes ({progress:.2f}%)", end='\r')

        print("\nArquivo enviado. Enviando sinal de EOF...")
        eof_payload = b'EOF'
        eof_header = struct.pack('>H', len(eof_payload))
        retries = 0
        eof_acked = False
        
        while not eof_acked and retries < MAX_RETRIES:
            ser.write(eof_header)
            response = wait_for_ack(ser)
            
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

    except Exception as e:
        print(f"\nErro durante o envio do arquivo: {e}")
        return False
    
def generate_arguments():
    parser = argparse.ArgumentParser(description="Enviar arquivos utilizando porta serial.")
    parser.add_argument("com", type=str, help="Nome da porta COM (ex: COM4 ou /dev/ttyUSB0).")
    parser.add_argument("velocity", type=int, help="Velocidade da porta COM (baud rate, ex: 9600).")
    parser.add_argument("path", type=str, help="Localização do arquivo a ser transferido.")
    return parser.parse_args()

def main():
    args = generate_arguments()
    
    if not os.path.exists(args.path):
        print(f"Erro: O arquivo '{args.path}' não foi encontrado.")
        sys.exit(1)

    ser = None
    try:
        ser = serial.Serial(args.com, args.velocity, timeout=TIMEOUT)
        print(f"Porta {args.com} aberta com sucesso.")

        if perform_handshake(ser):
            send_file_in_chunks(ser, args.path)
        else:
            print("Não foi possível estabelecer comunicação com o receptor.")

    except serial.SerialException as e:
        print(f"Erro ao abrir ou usar a porta serial: {e}")
    except KeyboardInterrupt:
        print("\n\nOperação cancelada pelo usuário. Fechando a porta...")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")
    finally:
        if ser and ser.is_open:
            ser.close()
            print("Porta COM fechada.")

if __name__ == "__main__":
    main()