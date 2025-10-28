import time
import serial

COM_PORT = 'COM4'
BAUD_RATE = 9600

def check_package(data):
    return data is not None and len(data) > 0 
    
def receive_package(data):
    data_str = data.decode('utf-8', errors='ignore')
    print(f"Pacote recebido: {data_str}")

def listen_port(ser):
    try:
        data = ser.readline().strip()

        if not data:
            return True

        if data == b'hello':
            print("Recebido handshake 'hello', respondendo 'hello-back'")
            ser.write(b'hello-back\n') 
        elif data == b'EOF':
            print("Recebido comando 'EOF'. Encerrando conexão.")
            return False 
        else:
            isOk = check_package(data)
            if not isOk:
                print("Pacote inválido recebido. Enviando NAK.")
                ser.write(b'NAK\n') 
            else:
                receive_package(data)
                print("Pacote válido. Enviando ACK.")
                ser.write(b'ACK\n')
        
        return True

    except serial.SerialException as e:
        print(f"Erro de comunicação serial: {e}")
        return False 
    except Exception as e:
        print(f"Erro inesperado ao receber dado: {e}")
        return True
            
    except Exception as e:
        print(f"Erro ao receber dado: {e}")


def main():
    ser = None
    
    try:
        ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
        print(f"Porta {COM_PORT} aberta com sucesso.")
        
        while True:
            if not listen_port(ser):
                break
            time.sleep(0.01)
    except Exception as e:
        print(f"Erro ao abrir a porta serial: {e}")
    finally:
        if ser and ser.is_open:
            ser.close()
            print(f"Porta {COM_PORT} fechada.")


if __name__ == "__main__":
    main()