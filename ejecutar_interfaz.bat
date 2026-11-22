@echo off
setlocal
cd /d "%~dp0"
rem Si MSYS2 esta en su ruta habitual, habilitar automaticamente NASM y GCC i686.
if exist "C:\msys64\mingw32\bin\gcc.exe" set "PATH=C:\msys64\mingw32\bin;C:\msys64\usr\bin;%PATH%"
where py >nul 2>&1
if not errorlevel 1 (
    py interfaz_grafica.py %*
) else (
    python interfaz_grafica.py %*
)
pause
