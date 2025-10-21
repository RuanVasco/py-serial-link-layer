#include <cstring>
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

// Função para descomprimir dados usando zlib (formato GZIP)
std::vector<char> decompress_data(const std::vector<char>& data) {
    z_stream zs;
    memset(&zs, 0, sizeof(zs));

    // O 16 + MAX_WBITS habilita a descompressão do formato GZIP
    if (inflateInit2(&zs, 16 + MAX_WBITS) != Z_OK) {
        throw std::runtime_error("inflateInit2 failed!");
    }

    zs.next_in = (Bytef*)data.data();
    zs.avail_in = data.size();

    int ret;
    char outbuffer[32768];
    std::vector<char> decompressed_data;

    do {
        zs.next_out = (Bytef*)outbuffer;
        zs.avail_out = sizeof(outbuffer);
        ret = inflate(&zs, 0);
        if (decompressed_data.size() < zs.total_out) {
            decompressed_data.insert(decompressed_data.end(), outbuffer, outbuffer + zs.total_out - decompressed_data.size());
        }
    } while (ret == Z_OK);

    inflateEnd(&zs);

    if (ret != Z_STREAM_END) {
        throw std::runtime_error("Exception during GZIP decompression: (" + std::to_string(ret) + ")");
    }

    return decompressed_data;
}

int configure_serial_port(const std::string& port_name) {
    int fd = open(port_name.c_str(), O_RDWR | O_NOCTTY);
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

    // Timeout de leitura: 0.5 segundos
    options.c_cc[VTIME] = 5;
    options.c_cc[VMIN] = 0;

    options.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);
    options.c_iflag &= ~(IXON | IXOFF | IXANY);
    options.c_oflag &= ~OPOST;

    tcsetattr(fd, TCSANOW, &options);
    return fd;
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Uso: " << argv[0] << " <porta_serial> <arquivo_de_saida>" << std::endl;
        return 1;
    }

    std::string port_name = argv[1];
    std::string output_filename = argv[2];

    try {
        // 1. Configurar e ler da porta serial
        int serial_port = configure_serial_port(port_name);
        std::cout << "Aguardando dados na porta " << port_name << "..." << std::endl;

        std::vector<char> received_data;
        char buffer[1024];
        ssize_t bytes_read;
        while ((bytes_read = read(serial_port, buffer, sizeof(buffer))) > 0) {
            received_data.insert(received_data.end(), buffer, buffer + bytes_read);
        }
        close(serial_port);
        std::cout << "Recebidos " << received_data.size() << " bytes." << std::endl;
        
        if (received_data.empty()) {
            throw std::runtime_error("Nenhum dado foi recebido.");
        }

        // 2. Descomprimir os dados
        std::cout << "Descomprimindo dados..." << std::endl;
        std::vector<char> decompressed_data = decompress_data(received_data);
        std::cout << "Tamanho original: " << decompressed_data.size() << " bytes." << std::endl;

        // 3. Salvar os dados em um arquivo
        std::ofstream file(output_filename, std::ios::binary);
        if (!file) {
            throw std::runtime_error("Não foi possível criar o arquivo de saída: " + output_filename);
        }
        file.write(decompressed_data.data(), decompressed_data.size());
        file.close();

        std::cout << "Arquivo salvo em " << output_filename << " com sucesso!" << std::endl;

    } catch (const std::exception& e) {
        std::cerr << "Erro: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}