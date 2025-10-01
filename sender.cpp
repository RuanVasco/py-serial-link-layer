#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <stdexcept>
#include <zlib.h>

// Para a comunicação serial (APIs do C/POSIX)
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <cstring>

// Função para comprimir dados usando zlib (formato GZIP)
std::vector<char> compress_data(const std::vector<char>& data) {
    z_stream zs;
    memset(&zs, 0, sizeof(zs));

    // O 16 + MAX_WBITS habilita a compressão em formato GZIP
    if (deflateInit2(&zs, Z_DEFAULT_COMPRESSION, Z_DEFLATED, 16 + MAX_WBITS, 8, Z_DEFAULT_STRATEGY) != Z_OK) {
        throw std::runtime_error("deflateInit2 failed!");
    }

    zs.next_in = (Bytef*)data.data();
    zs.avail_in = data.size();

    int ret;
    char outbuffer[32768];
    std::vector<char> compressed_data;

    do {
        zs.next_out = (Bytef*)outbuffer;
        zs.avail_out = sizeof(outbuffer);
        ret = deflate(&zs, Z_FINISH);
        if (compressed_data.size() < zs.total_out) {
            compressed_data.insert(compressed_data.end(), outbuffer, outbuffer + zs.total_out - compressed_data.size());
        }
    } while (ret == Z_OK);

    deflateEnd(&zs);

    if (ret != Z_STREAM_END) {
        throw std::runtime_error("Exception during GZIP compression: (" + std::to_string(ret) + ")");
    }

    return compressed_data;
}

// Função para configurar a porta serial
int configure_serial_port(const std::string& port_name) {
    int fd = open(port_name.c_str(), O_RDWR | O_NOCTTY | O_NDELAY);
    if (fd == -1) {
        throw std::runtime_error("Não foi possível abrir a porta serial: " + port_name);
    }

    struct termios options;
    tcgetattr(fd, &options);

    cfsetispeed(&options, B9600); // Velocidade de entrada
    cfsetospeed(&options, B9600); // Velocidade de saída

    options.c_cflag |= (CLOCAL | CREAD);
    options.c_cflag &= ~CSIZE;
    options.c_cflag |= CS8;       // 8 bits de dados
    options.c_cflag &= ~PARENB;    // Sem paridade
    options.c_cflag &= ~CSTOPB;    // 1 stop bit
    options.c_cflag &= ~CRTSCTS;   // Sem controle de fluxo por hardware

    // Modo "raw"
    options.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);
    options.c_iflag &= ~(IXON | IXOFF | IXANY);
    options.c_oflag &= ~OPOST;

    tcsetattr(fd, TCSANOW, &options);
    return fd;
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Uso: " << argv[0] << " <porta_serial> <arquivo_de_entrada>" << std::endl;
        return 1;
    }

    std::string port_name = argv[1];
    std::string input_filename = argv[2];

    try {
        // 1. Abrir e ler o arquivo de entrada
        std::ifstream file(input_filename, std::ios::binary);
        if (!file) {
            throw std::runtime_error("Não foi possível abrir o arquivo de entrada: " + input_filename);
        }
        std::vector<char> file_data((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
        file.close();

        // 2. Comprimir os dados
        std::cout << "Comprimindo " << file_data.size() << " bytes..." << std::endl;
        std::vector<char> compressed_data = compress_data(file_data);
        std::cout << "Tamanho comprimido: " << compressed_data.size() << " bytes." << std::endl;

        // 3. Configurar e enviar pela porta serial
        int serial_port = configure_serial_port(port_name);
        
        std::cout << "Enviando dados pela porta " << port_name << "..." << std::endl;
        ssize_t bytes_written = write(serial_port, compressed_data.data(), compressed_data.size());
        if (bytes_written == -1) {
            throw std::runtime_error("Erro ao escrever na porta serial.");
        }
        
        close(serial_port);
        std::cout << "Envio concluído!" << std::endl;

    } catch (const std::exception& e) {
        std::cerr << "Erro: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}