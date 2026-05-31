# Computer Service System

Projekt inżynierski: aplikacja Django do obsługi zleceń w serwisie komputerowym.

System pozwala zgłosić naprawę, wybrać usługę z katalogu i sprawdzić status zlecenia bez zakładania konta. Pracownik serwisu obsługuje zgłoszenia w panelu technika, a administrator zarządza kontami pracowników oraz ofertą usług.

## Wymagania

- Windows 10/11,
- Docker Desktop,
- Docker Compose,
- Git, jeżeli projekt jest pobierany z repozytorium.

Przed uruchomieniem projektu Docker Desktop musi być włączony.

## Technologie

- Python,
- Django,
- PostgreSQL,
- Docker Compose,
- HTML/CSS.

Projekt nie korzysta z Bootstrapa.

## Role w systemie

- Klient: wybiera usługę, tworzy zgłoszenie i śledzi status naprawy po numerze zlecenia oraz e-mailu albo telefonie.
- Technik: przyjmuje i obsługuje zlecenia, zmienia statusy, dodaje komentarze, załączniki, diagnozę i planowany termin realizacji.
- Administrator: zarządza kontami pracowników oraz katalogiem usług i cennikiem.

## Funkcje projektu

- katalog usług z opcjami i orientacyjną wyceną,
- formularz zgłoszenia naprawy,
- śledzenie statusu zlecenia bez logowania,
- panel technika do obsługi zgłoszeń,
- komentarze publiczne i wewnętrzne,
- załączniki do zleceń,
- historia zmian zlecenia,
- panel administratora do zarządzania kontami i usługami.

## Uruchomienie na Windows

Najprostszy sposób uruchomienia projektu:

```powershell
uruchom_projekt.bat
```

Po uruchomieniu aplikacja będzie dostępna pod adresem:

```text
http://127.0.0.1:8000/
```

Panel administratora:

```text
http://127.0.0.1:8000/admin/
```

Aby zatrzymać projekt, wróć do okna konsoli i naciśnij `CTRL+C`.

## Uruchomienie ręczne

Projekt można też uruchomić bez pliku `.bat`:

```powershell
docker compose up --build
```

Ta komenda buduje i uruchamia kontenery aplikacji Django oraz bazy danych PostgreSQL.

Zatrzymanie kontenerów:

```powershell
docker compose down
```

## Pierwsze uruchomienie

Projekt nie zawiera gotowych kont użytkowników. Pierwsze konto administratora należy utworzyć poleceniem:

```powershell
docker compose exec web python manage.py createsuperuser
```

Po zalogowaniu do panelu administratora można dodać konta techników i kolejne konta administratorów.

Przykładowe usługi można dodać komendą:

```powershell
docker compose exec web python manage.py seed_services
```

Komenda tworzy startowy katalog usług i opcje konfiguratora. Można uruchomić ją ponownie, bez dublowania tych samych danych.

## Baza danych

Główną bazą projektu jest PostgreSQL uruchamiany w Dockerze.

W `docker-compose.yml` baza działa w kontenerze na porcie `5432`, a na komputerze jest dostępna przez port `5433`. Dzięki temu nie koliduje z lokalną instalacją PostgreSQL.

W bazie zapisywane są między innymi:

- konta użytkowników,
- usługi i opcje konfiguratora,
- zlecenia serwisowe,
- komentarze, załączniki i historia zmian.

Plik `.env.example` pokazuje przykładową konfigurację dla ręcznego uruchamiania Django przy działającej bazie PostgreSQL:

```env
POSTGRES_DB=serwis_db
POSTGRES_USER=serwis_user
POSTGRES_PASSWORD=serwis_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
```

Jeżeli zmienna `POSTGRES_DB` nie jest ustawiona, aplikacja może uruchomić się na lokalnej bazie SQLite. Głównym trybem pracy projektu jest jednak PostgreSQL.

## Uwagi

Projekt nie korzysta z produkcyjnej wysyłki e-mail. Adres e-mail klienta służy do identyfikacji zgłoszenia podczas śledzenia statusu naprawy.
