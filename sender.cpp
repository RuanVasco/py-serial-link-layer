#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <stdexcept>
#include <zlib.h>
#include <cstdint> 

#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>

void compress_chunk(z_stream& zs, const std::vector<char>& chunk, std::vector<char>& compressed_output, int flush_mode) {
    compressed_output.clear();

    zs.next_in = (Bytef*)chunk.data();
    zs.avail_in = chunk.size();

    int ret;
    char outbuffer[32768];

    do {
        zs.next_out = (Bytef*)outbuffer;
        zs.avail_out = sizeof(outbuffer);
        ret = deflate(&zs, flush_mode);

        if (ret == Z_STREAM_ERROR) {
            throw std::runtime_error("Erro no stream de compressao zlib (deflate).");
        }

        size_t have = sizeof(outbuffer) - zs.avail_out;
        if (have > 0) {
            compressed_output.insert(compressed_output.end(), outbuffer, outbuffer + have);
        }

    } while (zs.avail_out == 0); 
}

int configure_serial_port(const std::string& port_name) {
    int fd = open(port_name.c_str(), O_RDWR | O_NOCTTY | O_NDELAY);
    if (fd == -1) {
        throw std::runtime_error("Não foi possível abrir a porta serial: " + port_name);
    }

    struct termios options;
    tcgetattr(fd, &options);

    cfsetispeed(&options, B9600); 
    cfsetospeed(&options, B9600); 

    options.c_cflag |= (CLOCAL | CREAD);
    options.c_cflag &= ~CSIZE;
    options.c_cflag |= CS8;      
    options.c_cflag &= ~PARENB;    
    options.c_cflag &= ~CSTOPB;    
    options.c_cflag &= ~CRTSCTS;   

    options.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);
    options.c_iflag &= ~(IXON | IXOFF | IXANY);
    options.c_oflag &= ~OPOST;

    tcsetattr(fd, TCSANOW, &options);
    return fd;
}

void send_package(int serial_port, const std::vector<char>& data) {
    if (data.empty()) return; 

    uint32_t package_size = data.size();
    if (write(serial_port, &package_size, sizeof(package_size)) != sizeof(package_size)) {
        throw std::runtime_error("Erro ao enviar o cabecalho do pacote.");
    }

    if (write(serial_port, data.data(), data.size()) != (ssize_t)data.size()) {
        throw std::runtime_error("Erro ao enviar os dados do pacote.");
    }
}

int main(int argc, char* argv[]) {
    const size_t CHUNK_SIZE = 4096; 

    if (argc != 3) {
        std::cerr << "Uso: " << argv[0] << " <porta_serial> <arquivo_de_entrada>" << std::endl;
        return 1;
    }

    std::string port_name = argv[1];
    std::string input_filename = argv[2];

    int serial_port = -1;

    try {
        std::ifstream file(input_filename, std::ios::binary);
        if (!file) {
            throw std::runtime_error("Não foi possível abrir o arquivo de entrada: " + input_filename);
        }

        serial_port = configure_serial_port(port_name);

        z_stream zs;
        memset(&zs, 0, sizeof(zs));
        if (deflateInit2(&zs, Z_DEFAULT_COMPRESSION, Z_DEFLATED, 16 + MAX_WBITS, 8, Z_DEFAULT_STRATEGY) != Z_OK) {
            throw std::runtime_error("deflateInit2 failed!");
        }

        bool connection_started = false;
        std::vector<char> message = "conecta";

        while(!connection_started) {
            compress_chunk(zs, message, output, EOF);
        }

        std::vector<char> read_buffer(CHUNK_SIZE);
        std::vector<char> compressed_buffer;

        std::cout << "Iniciando envio do arquivo '" << input_filename << "' para a porta " << port_name << "..." << std::endl;

        while (true) {
            file.read(read_buffer.data(), CHUNK_SIZE);
            std::streamsize bytes_read = file.gcount();

            if (bytes_read == 0) {
                break;
            }

            read_buffer.resize(bytes_read);

            int flush_mode = file.peek() == EOF ? Z_FINISH : Z_NO_FLUSH;
            
            compress_chunk(zs, read_buffer, compressed_buffer, flush_mode);
            send_package(serial_port, compressed_buffer);
            
            std::cout << "Enviado pacote: " << bytes_read << " bytes (originais) -> " << compressed_buffer.size() << " bytes (comprimidos)" << std::endl;
        }

        deflateEnd(&zs);
        
        uint32_t end_signal = 0;
        if (write(serial_port, &end_signal, sizeof(end_signal)) != sizeof(end_signal)) {
            throw std::runtime_error("Erro ao enviar sinal de fim de transmissao.");
        }

        close(serial_port);
        std::cout << "\nEnvio concluído com sucesso!" << std::endl;

    } catch (const std::exception& e) {
        std::cerr << "Erro: " << e.what() << std::endl;
        if (serial_port != -1) {
            close(serial_port);
        }
        return 1;
    }

    return 0;
}