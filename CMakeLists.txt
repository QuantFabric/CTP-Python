cmake_minimum_required(VERSION 3.21)   # OUTPUT_DIR 参数需要 3.21+
project(ctp_wrap LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---- CTP 版本与路径 ----
set(CTP_API_VERSION "6.7.13" CACHE STRING "CTP API version")

set(CTP_ROOT         "${CMAKE_CURRENT_SOURCE_DIR}/ctp/${CTP_API_VERSION}")
set(CTP_INCLUDE_DIR  "${CTP_ROOT}/include")
set(CTP_LIB_DIR      "${CTP_ROOT}/lib")

# ---- 定位依赖 ----
find_package(SWIG REQUIRED)
include(${SWIG_USE_FILE})
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)

# ---- 获取 Python 扩展 ABI 后缀（关键）----
# 优先用 sysconfig.get_config_var('EXT_SUFFIX')，直接拿到 ".cpython-313-x86_64-linux-gnu.so"
if(NOT PY_EXT_SUFFIX)
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
            "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX') or '')"
        OUTPUT_VARIABLE PY_EXT_SUFFIX
        OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE _py_ext_result
        ERROR_QUIET
    )
endif()

# 兜底：从 Python3_SOABI 拼装
if(NOT PY_EXT_SUFFIX AND Python3_SOABI)
    set(PY_EXT_SUFFIX ".${Python3_SOABI}")
endif()

if(NOT PY_EXT_SUFFIX)
    message(WARNING "未能获取 Python EXT_SUFFIX，将使用默认 .so 后缀")
endif()
message(STATUS "Python 扩展后缀: ${PY_EXT_SUFFIX}")

# ---- SWIG 生成目录----
set(SWIG_OUTPUT_DIR "${CMAKE_CURRENT_BINARY_DIR}/swig_output")
file(MAKE_DIRECTORY "${SWIG_OUTPUT_DIR}")
set(CMAKE_SWIG_FLAGS "-I${CTP_INCLUDE_DIR};-threads")
message(STATUS "CTP_INCLUDE_DIR = ${CTP_INCLUDE_DIR}")

# ---- 公共宏：配置一个 CTP 模块 ----
# target_name : CMake 目标名（不含下划线）
# module_name : SWIG %module 名（用于生成 OUTPUT_NAME "_<module_name>"）
macro(configure_ctp_module target_name module_name source_i ctp_lib)

    set_property(SOURCE ${source_i} PROPERTY CPLUSPLUS ON)
    swig_add_library(${target_name}
        TYPE MODULE
        LANGUAGE python
        SOURCES ${source_i}
        OUTPUT_DIR "${SWIG_OUTPUT_DIR}"
    )

    target_include_directories(${target_name} PRIVATE
        ${CTP_INCLUDE_DIR}
        ${Python3_INCLUDE_DIRS}
    )

    target_link_directories(${target_name} PRIVATE ${CTP_LIB_DIR})
    target_link_libraries(${target_name} PRIVATE ${ctp_lib})

    # MSVC 特定：启用标准异常处理
    if(MSVC)
        target_compile_options(${target_name} PRIVATE
            /EHsc        # 标准异常处理
            /bigobj      # 解决 C1128 节数超限
            /utf-8       # 解决 C4819 代码页 936 警告
            /wd4828      # 屏蔽 CTP 头文件 GBK 注释触发的 C4828
        )
        target_compile_definitions(${target_name} PRIVATE
            Py_NO_LINK_LIB   # 防止隐式链接错误的 python313.lib
        )
        # 可选：将Python库目录加入链接搜索路径
        if(Python3_LIBRARY_DIRS)
            target_link_directories(${target_name} PRIVATE ${Python3_LIBRARY_DIRS})
        endif()
    endif()

    set_target_properties(${target_name} PROPERTIES
        PREFIX ""
        OUTPUT_NAME "_${module_name}"
        SUFFIX      "${PY_EXT_SUFFIX}"
        LINKER_LANGUAGE CXX
    )
    # 仅 Unix-like 平台设置 RPATH（Windows 无 RPATH 机制）
    if(APPLE)
        set_target_properties(${target_name} PROPERTIES
            INSTALL_RPATH "@loader_path/lib"
            BUILD_RPATH   "@loader_path/lib"
        )
    elseif(UNIX)
        set_target_properties(${target_name} PROPERTIES
            INSTALL_RPATH "$ORIGIN/lib"
            BUILD_RPATH   "$ORIGIN/lib"
        )
    endif()
endmacro()

# ---- 交易接口 ----
configure_ctp_module(ctp_td ctp_td
    "${CMAKE_CURRENT_SOURCE_DIR}/src/ctp_td.i"
    thosttraderapi_se
)

# ---- 行情接口 ----
configure_ctp_module(ctp_md ctp_md
    "${CMAKE_CURRENT_SOURCE_DIR}/src/ctp_md.i"
    thostmduserapi_se
)

# ============================================================
# 安装规则
# ============================================================
# 1. SWIG 生成的 Python 壳
install(FILES "${SWIG_OUTPUT_DIR}/ctp_td.py" DESTINATION ctp_wrap)
install(FILES "${SWIG_OUTPUT_DIR}/ctp_md.py" DESTINATION ctp_wrap)

# 2. 编译产物（_ctp_td.*.so / _ctp_md.*.so）
install(TARGETS ctp_td ctp_md
    LIBRARY DESTINATION ctp_wrap
    RUNTIME DESTINATION ctp_wrap
)

# 3. 包的 __init__.py
set(_init_py "${SWIG_OUTPUT_DIR}/__init__.py")
file(WRITE "${_init_py}" "__version__ = \"${CTP_API_VERSION}\"\n")
install(FILES "${_init_py}" DESTINATION ctp_wrap)

# 4. CTP 原生动态库（按平台区分）
if(WIN32)
    install(FILES
        "${CTP_LIB_DIR}/thosttraderapi_se.dll"
        "${CTP_LIB_DIR}/thostmduserapi_se.dll"
        DESTINATION ctp_wrap
    )
else()
    install(FILES
        "${CTP_LIB_DIR}/libthosttraderapi_se.so"
        "${CTP_LIB_DIR}/libthostmduserapi_se.so"
        DESTINATION ctp_wrap/lib
    )
endif()