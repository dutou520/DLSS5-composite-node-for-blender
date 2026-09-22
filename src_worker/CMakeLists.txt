cmake_minimum_required(VERSION 3.20)
project(dlss5_worker LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(dlss5_worker
    main.cpp
    d3d12_dlssnr.h
    d3d12_dlssnr.cpp
    image_io.h
    stb_image.h
    stb_image_write.h
)

target_link_libraries(dlss5_worker PRIVATE
    d3d12
    dxgi
)

set_target_properties(dlss5_worker PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../bin"
)
