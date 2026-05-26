from decimal import Decimal

from django.core.management.base import BaseCommand

from orders.models import Service, ServiceOption, ServiceOptionGroup


def money(value: int) -> Decimal:
    return Decimal(str(value))


class Command(BaseCommand):
    help = "Tworzy lub aktualizuje przykładowe usługi widoczne w katalogu klienta."

    def handle(self, *args, **options):
        services = [
            {
                "name": "Czyszczenie i konserwacja układu chłodzenia",
                "description": (
                    "Czyszczenie układu chłodzenia, wymiana pasty termoprzewodzącej "
                    "oraz kontrola temperatur pracy urządzenia."
                ),
                "price_min": 120,
                "price_max": 220,
                "duration": 90,
                "groups": [
                    {
                        "name": "Zakres czyszczenia",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": True,
                        "sort": 1,
                        "options": [
                            ("Standardowe czyszczenie", 0, 0, 0, 1),
                            ("Pełna konserwacja z wymianą pasty", 40, 70, 20, 2),
                        ],
                    },
                    {
                        "name": "Dodatkowe czynności",
                        "type": ServiceOptionGroup.SelectionType.MULTI,
                        "required": False,
                        "sort": 2,
                        "options": [
                            ("Wymiana termopadów", 50, 100, 30, 1),
                            ("Test temperatur po serwisie", 30, 50, 20, 2),
                        ],
                    },
                ],
            },
            {
                "name": "Instalacja lub reinstalacja systemu operacyjnego",
                "description": (
                    "Instalacja systemu, sterowników oraz podstawowa konfiguracja "
                    "komputera po przygotowaniu urządzenia do pracy."
                ),
                "price_min": 140,
                "price_max": 260,
                "duration": 120,
                "groups": [
                    {
                        "name": "Rodzaj instalacji",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": True,
                        "sort": 1,
                        "options": [
                            ("Instalacja na czysto", 0, 0, 0, 1),
                            ("Reinstalacja z zachowaniem danych", 80, 140, 60, 2),
                        ],
                    },
                    {
                        "name": "Zakres konfiguracji",
                        "type": ServiceOptionGroup.SelectionType.MULTI,
                        "required": False,
                        "sort": 2,
                        "options": [
                            ("Instalacja sterowników", 0, 0, 0, 1),
                            ("Pakiet podstawowych programów", 40, 70, 30, 2),
                            ("Kopia danych użytkownika", 80, 160, 60, 3),
                        ],
                    },
                    {
                        "name": "Licencja Windows",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": True,
                        "sort": 3,
                        "options": [
                            ("Posiadam własny klucz/licencję Windows", 0, 0, 0, 1),
                            ("Potrzebuję konsultacji w sprawie licencji", 0, 0, 0, 2),
                        ],
                    },
                ],
            },
            {
                "name": "Usuwanie wirusów i optymalizacja systemu",
                "description": (
                    "Skanowanie systemu, usuwanie złośliwego oprogramowania oraz "
                    "podstawowa optymalizacja działania komputera."
                ),
                "price_min": 100,
                "price_max": 220,
                "duration": 120,
                "groups": [
                    {
                        "name": "Zakres usługi",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": True,
                        "sort": 1,
                        "options": [
                            ("Usunięcie zagrożeń", 0, 0, 0, 1),
                            ("Usunięcie zagrożeń i pełna optymalizacja", 60, 100, 45, 2),
                        ],
                    },
                    {
                        "name": "Dodatkowe czynności",
                        "type": ServiceOptionGroup.SelectionType.MULTI,
                        "required": False,
                        "sort": 2,
                        "options": [
                            ("Aktualizacja systemu i programów", 30, 60, 30, 1),
                            ("Konfiguracja podstawowych zabezpieczeń", 40, 80, 30, 2),
                        ],
                    },
                ],
            },
            {
                "name": "Wymiana dysku HDD/SSD",
                "description": (
                    "Montaż lub wymiana dysku twardego albo SSD, z możliwością "
                    "migracji danych ze starego nośnika."
                ),
                "price_min": 100,
                "price_max": 220,
                "duration": 90,
                "groups": [
                    {
                        "name": "Migracja danych",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": False,
                        "sort": 1,
                        "options": [
                            ("Bez migracji danych", 0, 0, 0, 1),
                            ("Migracja danych do 250 GB", 80, 140, 60, 2),
                            ("Migracja danych powyżej 250 GB", 150, 260, 120, 3),
                        ],
                    },
                    {
                        "name": "Nośnik",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": False,
                        "sort": 2,
                        "options": [
                            ("Mam własny dysk do montażu", 0, 0, 0, 1),
                            ("Potrzebuję pomocy w doborze dysku", 30, 60, 30, 2),
                        ],
                    },
                ],
            },
            {
                "name": "Rozbudowa pamięci RAM",
                "description": (
                    "Dobór i montaż pamięci RAM w laptopie lub komputerze "
                    "stacjonarnym wraz z podstawową kontrolą działania."
                ),
                "price_min": 80,
                "price_max": 180,
                "duration": 60,
                "groups": [
                    {
                        "name": "Zakres rozbudowy",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": True,
                        "sort": 1,
                        "options": [
                            ("Mam własną pamięć RAM do montażu", 0, 0, 0, 1),
                            ("Potrzebuję doboru i montażu pamięci RAM", 40, 80, 30, 2),
                        ],
                    },
                    {
                        "name": "Testy",
                        "type": ServiceOptionGroup.SelectionType.MULTI,
                        "required": False,
                        "sort": 2,
                        "options": [
                            ("Test stabilności pamięci", 30, 60, 30, 1),
                        ],
                    },
                ],
            },
            {
                "name": "Wymiana klawiatury lub baterii w laptopie",
                "description": (
                    "Wymiana uszkodzonej klawiatury lub baterii w laptopie oraz "
                    "sprawdzenie poprawności działania po montażu."
                ),
                "price_min": 120,
                "price_max": 280,
                "duration": 90,
                "groups": [
                    {
                        "name": "Rodzaj naprawy",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": True,
                        "sort": 1,
                        "options": [
                            ("Wymiana klawiatury", 0, 60, 0, 1),
                            ("Wymiana baterii", 0, 60, 0, 2),
                            ("Weryfikacja zasilania i klawiatury", 40, 80, 30, 3),
                        ],
                    },
                    {
                        "name": "Część zamienna",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": False,
                        "sort": 2,
                        "options": [
                            ("Mam własną część zamienną", 0, 0, 0, 1),
                            ("Potrzebuję pomocy w doborze części", 30, 70, 30, 2),
                        ],
                    },
                ],
            },
            {
                "name": "Odzyskiwanie danych z dysku",
                "description": (
                    "Próba odzyskania danych z dysku w przypadku usunięcia plików, "
                    "problemów z systemem plików lub błędów nośnika."
                ),
                "price_min": 150,
                "price_max": 500,
                "duration": 180,
                "groups": [
                    {
                        "name": "Zakres odzyskiwania",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": True,
                        "sort": 1,
                        "options": [
                            ("Odzyskiwanie po usunięciu plików", 0, 80, 60, 1),
                            ("Nośnik z błędami logicznymi", 100, 250, 120, 2),
                        ],
                    },
                    {
                        "name": "Sposób przekazania danych",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": False,
                        "sort": 2,
                        "options": [
                            ("Kopia na mój nośnik", 0, 0, 0, 1),
                            ("Przygotowanie danych do odbioru", 40, 80, 30, 2),
                        ],
                    },
                ],
            },
            {
                "name": "Inne / indywidualna diagnoza",
                "description": (
                    "Opcja dla problemów, które nie pasują do pozostałych usług. "
                    "Opisz objawy w formularzu, a serwis określi dalszy zakres prac."
                ),
                "pricing_mode": Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
                "price_min": 0,
                "price_max": 0,
                "duration": 0,
                "groups": [
                    {
                        "name": "Rodzaj problemu",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": False,
                        "sort": 1,
                        "options": [
                            ("Problem ze sprzętem", 0, 0, 0, 1),
                            ("Problem z systemem lub programami", 0, 0, 0, 2),
                            ("Nie wiem - proszę o diagnozę", 0, 0, 0, 3),
                        ],
                    },
                ],
            },
        ]

        desired_names = {service_data["name"] for service_data in services}
        legacy_names = {
            "Czyszczenie laptopa",
            "Diagnostyka komputera",
            "Instalacja systemu operacyjnego",
            "Wymiana dysku na SSD",
        }

        for service_data in services:
            service, _created = Service.objects.update_or_create(
                name=service_data["name"],
                defaults={
                    "description": service_data["description"],
                    "pricing_mode": service_data.get(
                        "pricing_mode",
                        Service.PricingMode.CONFIGURABLE,
                    ),
                    "base_price_min": money(service_data["price_min"]),
                    "base_price_max": money(service_data["price_max"]),
                    "base_duration_minutes": service_data["duration"],
                    "is_active": True,
                },
            )

            active_group_ids = []
            for group_data in service_data["groups"]:
                group, _created = ServiceOptionGroup.objects.update_or_create(
                    service=service,
                    name=group_data["name"],
                    defaults={
                        "selection_type": group_data["type"],
                        "is_required": group_data["required"],
                        "sort_order": group_data["sort"],
                        "is_active": True,
                    },
                )
                active_group_ids.append(group.id)

                active_option_ids = []
                for option_name, delta_min, delta_max, duration_delta, sort in group_data[
                    "options"
                ]:
                    option, _created = ServiceOption.objects.update_or_create(
                        group=group,
                        name=option_name,
                        defaults={
                            "price_delta_min": money(delta_min),
                            "price_delta_max": money(delta_max),
                            "duration_delta_minutes": duration_delta,
                            "sort_order": sort,
                            "is_active": True,
                        },
                    )
                    active_option_ids.append(option.id)

                group.options.exclude(id__in=active_option_ids).update(is_active=False)

            service.option_groups.exclude(id__in=active_group_ids).update(is_active=False)

        Service.objects.filter(name__in=legacy_names).exclude(name__in=desired_names).update(
            is_active=False
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Gotowe: dodano lub zaktualizowano katalog usług ({len(services)} pozycji)."
            )
        )
