@echo off
setlocal

cd /d "%~dp0backend"

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Nie znaleziono pliku .venv\Scripts\python.exe.
    echo Sprawdz, czy srodowisko wirtualne .venv istnieje w katalogu projektu.
    pause
    exit /b 1
)

echo.
echo Uruchamiam projekt inzynierski...
echo.
echo Adresy:
echo   Katalog uslug:      http://127.0.0.1:8000/services/
echo   Sledzenie zlecenia: http://127.0.0.1:8000/track/
echo   Panel technika:     http://127.0.0.1:8000/tech/dashboard/
echo   Panel admina:       http://127.0.0.1:8000/admin/
echo.
echo Aby zatrzymac serwer, wcisnij CTRL+C w tym oknie.
echo.

start "" "http://127.0.0.1:8000/"
"%~dp0.venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000

pause
