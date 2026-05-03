# System zarządzania procesem obsługi zleceń w serwisie komputerowym

Projekt inżynierski: system do obsługi zleceń serwisowych z panelem klienta, technika i administratora.

## Moduły (plan)
- Katalog usług z konfiguracją i wyceną
- Zlecenia serwisowe + statusy
- Panel technika + komentarze
- Audit log
- Guest access
- Powiadomienia e-mail

## Uruchamianie lokalne

Najprostszy sposób na Windows:

1. Uruchom plik `uruchom_projekt.bat` z katalogu głównego projektu.
2. Otwórz w przeglądarce `http://127.0.0.1:8000/services/`.
3. Aby zatrzymać serwer, naciśnij `CTRL+C` w oknie konsoli.

Ręczne uruchomienie z PowerShella:

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py runserver
```

## Dane przykładowe

Projekt zawiera komendę tworzącą przykładowy katalog usług i opcje konfiguratora.
Komenda jest idempotentna, więc można uruchamiać ją wiele razy bez dublowania danych.

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py seed_services
```
