# Serwis komputerowy

Projekt inżynierski: aplikacja do obsługi zleceń w serwisie komputerowym.

Klient może wybrać usługę z katalogu, utworzyć zgłoszenie naprawy i sprawdzić status zlecenia bez zakładania konta. Pracownik serwisu obsługuje zgłoszenia w panelu technika, a administrator zarządza kontami pracowników oraz ofertą usług.

## Co zawiera projekt

- katalog usług z opcjami i orientacyjną wyceną,
- formularz zgłoszenia naprawy,
- śledzenie statusu zlecenia po numerze zlecenia oraz e-mailu albo telefonie,
- panel technika do obsługi zgłoszeń, komentarzy, załączników i statusów,
- panel administratora do zarządzania kontami pracowników oraz usługami,
- historia zmian zlecenia.

## Uruchomienie na Windows

Najprościej uruchomić projekt plikiem:

```powershell
uruchom_projekt.bat
```

Po uruchomieniu strona będzie dostępna pod adresem:

```text
http://127.0.0.1:8000/
```

Aby zatrzymać projekt, wróć do okna konsoli i naciśnij `CTRL+C`.

## Uruchomienie ręczne

Projekt działa przez Docker Compose. Przed startem musi być uruchomiony Docker Desktop.

```powershell
docker compose up --build
```

Docker uruchamia:

- `web` - aplikację Django,
- `db` - bazę PostgreSQL.

PostgreSQL działa w kontenerze na porcie `5432`, a na komputerze jest wystawiony jako `5433`, żeby nie kolidował z lokalną instalacją PostgreSQL.

Zatrzymanie kontenerów:

```powershell
docker compose down
```

## Pierwsze uruchomienie

Po starcie projektu można dodać przykładowe usługi:

```powershell
docker compose exec web python manage.py seed_services
```

Komenda tworzy przykładowy katalog usług i opcje konfiguratora. Można uruchamiać ją ponownie, bez dublowania tych samych danych.

Projekt nie zawiera gotowych kont użytkowników. Pierwsze konto administratora tworzy się poleceniem:

```powershell
docker compose exec web python manage.py createsuperuser
```

Po zalogowaniu do panelu administratora można utworzyć konta techników i kolejne konta administratorów.

## Baza danych

Główną bazą projektu jest PostgreSQL uruchamiany przez Docker Compose. Zlecenia, usługi i konta użytkowników zapisują się w bazie danych.

Plik `.env.example` pokazuje przykładową konfigurację dla ręcznego uruchamiania Django przy działającej bazie PostgreSQL:

```env
POSTGRES_DB=serwis_db
POSTGRES_USER=serwis_user
POSTGRES_PASSWORD=serwis_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
```

Jeżeli zmienna `POSTGRES_DB` nie jest ustawiona, projekt może uruchomić się awaryjnie na lokalnej bazie SQLite. W tym projekcie głównym trybem pracy jest jednak PostgreSQL.

## Uwagi

Projekt nie korzysta z wysyłki e-mail. Adres e-mail klienta służy do identyfikacji zgłoszenia podczas śledzenia statusu naprawy.
