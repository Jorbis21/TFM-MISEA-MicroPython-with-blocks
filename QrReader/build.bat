@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================
echo   Construyendo QrReader portable
echo ================================================
echo.

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo Ejecutando PyInstaller...
echo.
C:\Python314\python.exe -m PyInstaller QrReader.spec
if %errorlevel% neq 0 (
    echo.
    echo La construccion con PyInstaller ha fallado. Revisa los errores de arriba.
    pause
    exit /b 1
)

echo.
if exist ".env" (
    echo Copiando .env desde la raiz del proyecto a dist\QrReader\...
    copy /y ".env" "dist\QrReader\.env" >nul
    echo Hecho.
) else (
    echo ================================================
    echo   AVISO: no se encuentra ".env" aqui, en la raiz del proyecto.
    echo   La app arrancara sin clave de Gemini hasta que crees uno.
    echo   Crea un archivo ".env" en esta misma carpeta con una linea:
    echo   GEMINI_API_KEY=tu_clave_aqui
    echo   y vuelve a ejecutar este script.
    echo ================================================
)

echo.
echo ================================================
echo   Build completa. Resultado en dist\QrReader\
echo ================================================
pause
