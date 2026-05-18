# System zarządzania procesem obsługi zleceń w serwisie komputerowym

Projekt inżynierski: system do obsługi zleceń serwisowych z panelem klienta, technika i administratora.

## Zakres systemu
- Katalog usług z konfiguracją, wyceną i szacowanym czasem realizacji
- Zlecenia serwisowe, statusy i historia zmian
- Panel technika z przypisywaniem zleceń, diagnozą, komentarzami i załącznikami
- Panel administratora do zarządzania ofertą i danymi systemu
- Śledzenie zlecenia bez zakładania konta klienta
- Powiadomienia e-mail

## Uruchamianie lokalne

Najprostszy sposób na Windows:

1. Uruchom plik `uruchom_projekt.bat` z katalogu głównego projektu.
2. Otwórz w przeglądarce `http://127.0.0.1:8000/`.
3. Aby zatrzymać serwer, naciśnij `CTRL+C` w oknie konsoli.

Ręczne uruchomienie z PowerShella:

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py runserver
```

## Konfiguracja bazy danych

Projekt może korzystać z PostgreSQL. Przed uruchomieniem skopiuj plik `.env.example` do `.env`
i uzupełnij dane połączenia do lokalnej bazy:

```env
POSTGRES_DB=serwis_db
POSTGRES_USER=serwis_user
POSTGRES_PASSWORD=twoje_haslo
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

Jeśli zmienna `POSTGRES_DB` nie jest ustawiona, projekt awaryjnie uruchomi się na lokalnej bazie SQLite.

## Dane przykładowe

Projekt zawiera komendę tworzącą przykładowy katalog usług i opcje konfiguratora.
Komenda jest idempotentna, więc można uruchamiać ją wiele razy bez dublowania danych.

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py seed_services
```
