cmake_minimum_required(VERSION 3.10)
project(SerialTransfer CXX)

# Encontrar a biblioteca zlib
find_package(ZLIB REQUIRED)

# Adicionar o executável do emissor
add_executable(sender sender.cpp)
# Linkar o emissor com zlib
target_link_libraries(sender PRIVATE ${ZLIB_LIBRARIES})

# Adicionar o executável do receptor
add_executable(receiver receiver.cpp)
# Linkar o receptor com zlib
target_link_libraries(receiver PRIVATE ${ZLIB_LIBRARIES})

# Definir o padrão C++
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)