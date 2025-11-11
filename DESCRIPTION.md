Descritivo da Implementação do Protocolo
1. Camada Física:
-Utilizamos um cabo serial conectado às portas seriais de dois microcomputadores.
-A comunicação é feita via protocolo RS-232, garantindo transmissão ponto a ponto.
-Configuração padrão: baud rate 9600, 8 bits de dados, sem paridade, 1 stop bit.


2. Camada de Enlace:
Implementamos uma máquina de estados para controlar a comunicação:
-AWAIT_HANDSHAKE: aguarda sincronização inicial.
-AWAIT_DATA: recebe ou envia dados após handshake.

Estrutura do pacote:
-SOH (Start of Header): byte inicial (0x01).
-Tipo: 2 bytes (definido pelo PacketType).
-Tamanho do payload: 2 bytes.
-Dados: serializados em JSON (com base64 para binário).
-CRC32: 4 bytes para detecção de erros.

Controle de fluxo:
-ACK/NAK para confirmar ou rejeitar pacotes.
-Timeout e retentativas configuráveis.

Detecção e correção de erros:
-CRC32 para validar integridade.
-Reenvio automático em caso de NAK ou timeout.


3. Camada de Aplicação
Desenvolvemos dois programas:
-Emissor: lê arquivo local, divide em chunks e envia via serial.
-Receptor: reconstrói arquivo a partir dos pacotes recebidos.

Recursos:
-Handshake inicial para sincronização.
-Envio em blocos (data_size configurável).
-Finalização com pacote EOF.
-Barra de progresso textual e logs para acompanhamento.

Principais Estruturas e Lógica
Classes:
Packet: monta e valida pacotes (inclui CRC e serialização).
PacketType: enum com tipos de pacotes (HANDSHAKE, DATA, EOF, ACK, NAK, etc.).
ConnectionParams: parâmetros de conexão (timeout, tamanho do chunk, número de tentativas).


Lógica de comunicação:
-Baseada em estado + confirmação (ACK/NAK).
-Retentativas automáticas para garantir confiabilidade.
-Reset de conexão quando necessário.

Diagrama ASCII da Arquitetura e Fluxo
+-----------------------------------------------------------+
|                      Camada de Aplicação                 |
|-----------------------------------------------------------|
| Emissor: lê arquivo -> divide em chunks -> envia pacotes |
| Receptor: reconstrói arquivo -> confirma -> salva        |
+-----------------------------------------------------------+
                |                           ^
                v                           |
+-----------------------------------------------------------+
|                      Camada de Enlace                    |
|-----------------------------------------------------------|
| Controle de fluxo: ACK / NAK / Timeout                   |
| Estrutura do pacote: SOH | TYPE | LENGTH | DATA | CRC    |
| Estados: AWAIT_HANDSHAKE -> AWAIT_DATA -> EOF            |
+-----------------------------------------------------------+
                |                           ^
                v                           |
+-----------------------------------------------------------+
|                      Camada Física                       |
|-----------------------------------------------------------|
| Cabo serial RS-232 conectado às portas COM              |
| Comunicação ponto a ponto (baud rate 9600)              |
+-----------------------------------------------------------+

Fluxo de Pacotes:
[Emissor] --HANDSHAKE--> [Receptor]
[Receptor] <--ACK-------- [Emissor]
[Emissor] --DATA(chunk)--> [Receptor]
[Receptor] <--ACK--------- [Emissor]
... (repetição até EOF)
[Emissor] --EOF----------> [Receptor]
[Receptor] <--ACK--------- [Emissor]