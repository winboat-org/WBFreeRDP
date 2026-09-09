# Applied after project() so platform defaults cannot restore .so lookup.
set(CMAKE_FIND_LIBRARY_SUFFIXES .a)
include_guard(GLOBAL)
set(WBFREERDP_STATIC_PREFIX "/work/prefix" CACHE PATH "Static dependency installation")

function(wb_portable_runtime)
  target_compile_definitions(winpr PRIVATE WITH_WBFREERDP_PCSC_STATIC)
  target_link_libraries(winpr PRIVATE "${WBFREERDP_STATIC_PREFIX}/lib/libwb-pcsclite.a")
  target_sources(xfreerdp PRIVATE "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/runtime.c")
  target_include_directories(xfreerdp PRIVATE "${WBFREERDP_STATIC_PREFIX}/include")
  target_link_options(xfreerdp PRIVATE "LINKER:--wrap=main")
endfunction()

cmake_language(DEFER DIRECTORY "${CMAKE_SOURCE_DIR}" CALL wb_portable_runtime)
