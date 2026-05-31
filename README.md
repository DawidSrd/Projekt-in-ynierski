# System zarządzania procesem obsługi zleceń w serwisie komputerowym

Projekt inżynierski: system do obsługi zleceń serwisowych z panelem klienta, technika i administratora.

## Zakres systemu
- Katalog usług z konfiguracją, wyceną i szacowanym czasem realizacji
- Zlecenia serwisowe, statusy i historia zmian
- Panel technika z przypisywaniem zleceń, diagnozą, komentarzami i załącznikami
- Panel administratora do zarządzania kontami pracowników oraz ofertą usług
- Śledzenie zlecenia bez zakładania konta klienta

## Uruchamianie projektu

Najprostszy sposób na Windows:

1. Uruchom plik `uruchom_projekt.bat` z katalogu głównego projektu.
2. Otwórz w przeglądarce `http://127.0.0.1:8000/`.
3. Aby zatrzymać serwer, naciśnij `CTRL+C` w oknie konsoli.

Plik `uruchom_projekt.bat` uruchamia aplikację przez Docker Compose, czyli z bazą PostgreSQL.
Przed uruchomieniem musi działać Docker Desktop.

Ręczne uruchomienie z PowerShella:

```powershell
docker compose up --build
```

## Docker i PostgreSQL

Docker Compose uruchamia dwie usługi:
- `web` - aplikacja Django
- `db` - baza PostgreSQL

Baza PostgreSQL działa w kontenerze na porcie `5432`, a na komputerze jest wystawiona jako `5433`, żeby nie kolidować z lokalną instalacją PostgreSQL.

Po uruchomieniu aplikacja będzie dostępna pod adresem:

```text
http://127.0.0.1:8000/
```

Po pierwszym uruchomieniu można dodać przykładowe usługi:

```powershell
docker compose exec web python manage.py seed_services
```

Konto administratora można utworzyć poleceniem:

```powershell
docker compose exec web python manage.py createsuperuser
```

Zatrzymanie kontenerów:

```powershell
docker compose down
```

## Konfiguracja bazy danych

Główną bazą projektu jest PostgreSQL uruchamiany przez Docker Compose. Zlecenia utworzone w aplikacji uruchomionej przez `docker compose up` albo `uruchom_projekt.bat` zapisują się w bazie PostgreSQL.

Plik `.env.example` pokazuje konfigurację dla ręcznego uruchamiania Django z PowerShella przy jednocześnie działającej bazie PostgreSQL z Dockera:

```env
POSTGRES_DB=serwis_db
POSTGRES_USER=serwis_user
POSTGRES_PASSWORD=serwis_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
```

Jeśli zmienna `POSTGRES_DB` nie jest ustawiona, projekt awaryjnie uruchomi się na lokalnej bazie SQLite. Ten tryb jest traktowany tylko jako techniczna alternatywa, a nie główny sposób pracy nad projektem.

## Dane przykładowe

Projekt zawiera komendę tworzącą przykładowy katalog usług i opcje konfiguratora.
Komenda jest idempotentna, więc można uruchamiać ją wiele razy bez dublowania danych.

```powershell
docker compose exec web python manage.py seed_services
```
