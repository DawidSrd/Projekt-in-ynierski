@echo off
setlocal

cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
    echo Nie znaleziono komendy docker.
    echo Zainstaluj Docker Desktop albo sprawdz, czy docker jest dostepny w PATH.
    pause
    exit /b 1
)

docker version >nul 2>nul
if errorlevel 1 (
    echo Docker Desktop nie jest uruchomiony.
    echo Uruchom Docker Desktop, poczekaj az silnik bedzie gotowy i wlacz ten plik ponownie.
    pause
    exit /b 1
)

echo.
echo Uruchamiam projekt inzynierski w Dockerze z baza PostgreSQL...
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
docker compose up --build

pause
