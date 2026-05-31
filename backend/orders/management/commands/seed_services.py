from decimal import Decimal

from django.core.management.base import BaseCommand

from orders.models import Service, ServiceOption, ServiceOptionGroup


def money(value: int) -> Decimal:
    return Decimal(str(value))


def single_group(name, options, required=True, sort=1):
    return {
        "name": name,
        "type": ServiceOptionGroup.SelectionType.SINGLE,
        "required": required,
        "sort": sort,
        "options": options,
    }


def multi_group(name, options, sort=2):
    return {
        "name": name,
        "type": ServiceOptionGroup.SelectionType.MULTI,
        "required": False,
        "sort": sort,
        "options": options,
    }


class Command(BaseCommand):
    help = "Tworzy lub aktualizuje przykładowe usługi widoczne w katalogu klienta."

    def handle(self, *args, **options):
        rename_existing_services = {
            "Czyszczenie i konserwacja układu chłodzenia": "Diagnostyka komputera lub laptopa",
            "Instalacja lub reinstalacja systemu operacyjnego": "Czyszczenie i konserwacja laptopa/PC",
            "Usuwanie wirusów i optymalizacja systemu": "Instalacja systemu Windows",
            "Wymiana klawiatury lub baterii w laptopie": "Naprawa systemu i usuwanie wirusów",
            "Odzyskiwanie danych z dysku": "Klonowanie dysku i przeniesienie danych",
        }
        for old_name, new_name in rename_existing_services.items():
            Service.objects.filter(name=old_name).update(name=new_name)

        services = [
            {
                "name": "Diagnostyka komputera lub laptopa",
                "description": "Gdy nie wiadomo, co powoduje problem. Serwis sprawdzi sprzęt i system oraz zaproponuje dalsze kroki.",
                "price_min": 80,
                "price_max": 160,
                "duration": 60,
                "groups": [
                    single_group(
                        "Rodzaj urządzenia",
                        [
                            ("Laptop", 0, 0, 0, 1),
                            ("Komputer stacjonarny", 0, 0, 0, 2),
                            ("Nie wiem - proszę o ocenę", 0, 0, 0, 3),
                        ],
                    )
                ],
            },
            {
                "name": "Czyszczenie i konserwacja laptopa/PC",
                "description": "Dla urządzeń, które się grzeją, głośno pracują albo dawno nie były czyszczone.",
                "price_min": 120,
                "price_max": 220,
                "duration": 90,
                "groups": [
                    single_group(
                        "Zakres czyszczenia",
                        [
                            ("Standardowe czyszczenie", 0, 0, 0, 1),
                            ("Pełna konserwacja z wymianą pasty", 40, 70, 20, 2),
                        ],
                    ),
                    multi_group(
                        "Dodatkowe czynności",
                        [
                            ("Wymiana termopadów", 50, 100, 30, 1),
                            ("Test temperatur po serwisie", 30, 50, 20, 2),
                        ],
                    ),
                ],
            },
            {
                "name": "Instalacja systemu Windows",
                "description": "Instalacja systemu, sterowników i podstawowa konfiguracja komputera do pracy.",
                "price_min": 140,
                "price_max": 260,
                "duration": 120,
                "groups": [
                    single_group(
                        "Rodzaj instalacji",
                        [
                            ("Instalacja na czysto", 0, 0, 0, 1),
                            ("Reinstalacja z zachowaniem danych", 80, 140, 60, 2),
                        ],
                    ),
                    multi_group(
                        "Zakres konfiguracji",
                        [
                            ("Instalacja sterowników", 0, 0, 0, 1),
                            ("Pakiet podstawowych programów", 40, 70, 30, 2),
                            ("Kopia danych użytkownika", 80, 160, 60, 3),
                        ],
                    ),
                    single_group(
                        "Licencja Windows",
                        [
                            ("Posiadam własny klucz/licencję Windows", 0, 0, 0, 1),
                            ("Potrzebuję konsultacji w sprawie licencji", 0, 0, 0, 2),
                        ],
                        sort=3,
                    ),
                ],
            },
            {
                "name": "Wymiana dysku HDD/SSD",
                "description": "Montaż nowego dysku z możliwością przeniesienia danych ze starego nośnika.",
                "price_min": 100,
                "price_max": 220,
                "duration": 90,
                "groups": [
                    single_group(
                        "Migracja danych",
                        [
                            ("Bez migracji danych", 0, 0, 0, 1),
                            ("Migracja danych do 250 GB", 80, 140, 60, 2),
                            ("Migracja danych powyżej 250 GB", 150, 260, 120, 3),
                        ],
                        required=False,
                    ),
                    single_group(
                        "Nośnik",
                        [
                            ("Mam własny dysk do montażu", 0, 0, 0, 1),
                            ("Potrzebuję pomocy w doborze dysku", 30, 60, 30, 2),
                        ],
                        required=False,
                        sort=2,
                    ),
                ],
            },
            {
                "name": "Rozbudowa pamięci RAM",
                "description": "Dobór i montaż pamięci RAM oraz sprawdzenie działania komputera po rozbudowie.",
                "price_min": 80,
                "price_max": 180,
                "duration": 60,
                "groups": [
                    single_group(
                        "Zakres rozbudowy",
                        [
                            ("Mam własną pamięć RAM do montażu", 0, 0, 0, 1),
                            ("Potrzebuję doboru i montażu pamięci RAM", 40, 80, 30, 2),
                        ],
                    ),
                    multi_group("Testy", [("Test stabilności pamięci", 30, 60, 30, 1)]),
                ],
            },
            {
                "name": "Naprawa systemu i usuwanie wirusów",
                "description": "Dla komputerów działających wolno, zawieszających się albo podejrzanych o infekcję.",
                "price_min": 100,
                "price_max": 220,
                "duration": 120,
                "groups": [
                    single_group(
                        "Zakres usługi",
                        [
                            ("Naprawa systemu", 0, 80, 30, 1),
                            ("Usuwanie wirusów i optymalizacja", 60, 120, 60, 2),
                        ],
                    ),
                    multi_group(
                        "Dodatkowe czynności",
                        [
                            ("Aktualizacja systemu i programów", 30, 60, 30, 1),
                            ("Konfiguracja podstawowych zabezpieczeń", 40, 80, 30, 2),
                        ],
                    ),
                ],
            },
            {
                "name": "Klonowanie dysku i przeniesienie danych",
                "description": "Przeniesienie systemu lub danych na nowy dysk, jeśli stan starego nośnika na to pozwala.",
                "price_min": 120,
                "price_max": 260,
                "duration": 120,
                "groups": [
                    single_group(
                        "Zakres przeniesienia",
                        [
                            ("Przeniesienie danych użytkownika", 0, 80, 60, 1),
                            ("Klonowanie całego systemu", 80, 160, 90, 2),
                        ],
                    )
                ],
            },
            {
                "name": "Odzyskiwanie danych",
                "description": "Próba odzyskania plików po usunięciu danych, awarii systemu albo problemach z dyskiem.",
                "price_min": 150,
                "price_max": 500,
                "duration": 180,
                "groups": [
                    single_group(
                        "Zakres odzyskiwania",
                        [
                            ("Odzyskiwanie po usunięciu plików", 0, 80, 60, 1),
                            ("Nośnik z błędami logicznymi", 100, 250, 120, 2),
                        ],
                    ),
                    single_group(
                        "Sposób przekazania danych",
                        [
                            ("Kopia na mój nośnik", 0, 0, 0, 1),
                            ("Przygotowanie danych do odbioru", 40, 80, 30, 2),
                        ],
                        required=False,
                        sort=2,
                    ),
                ],
            },
            {
                "name": "Wymiana matrycy w laptopie",
                "description": "Dla laptopów z uszkodzonym ekranem, pękniętą matrycą albo problemami z obrazem.",
                "price_min": 160,
                "price_max": 360,
                "duration": 120,
                "groups": [
                    single_group(
                        "Część zamienna",
                        [
                            ("Mam własną matrycę", 0, 0, 0, 1),
                            ("Potrzebuję doboru części", 40, 100, 30, 2),
                        ],
                        required=False,
                    )
                ],
            },
            {
                "name": "Wymiana klawiatury lub baterii",
                "description": "Dla laptopów z uszkodzoną klawiaturą albo zużytą baterią.",
                "price_min": 120,
                "price_max": 280,
                "duration": 90,
                "groups": [
                    single_group(
                        "Rodzaj naprawy",
                        [
                            ("Wymiana klawiatury", 0, 60, 0, 1),
                            ("Wymiana baterii", 0, 60, 0, 2),
                            ("Weryfikacja zasilania i klawiatury", 40, 80, 30, 3),
                        ],
                    ),
                    single_group(
                        "Część zamienna",
                        [
                            ("Mam własną część zamienną", 0, 0, 0, 1),
                            ("Potrzebuję pomocy w doborze części", 30, 70, 30, 2),
                        ],
                        required=False,
                        sort=2,
                    ),
                ],
            },
            {
                "name": "Inne / indywidualna diagnoza",
                "description": "Dla problemów, które nie pasują do standardowych usług. Opisz objawy, a serwis określi możliwy zakres prac.",
                "pricing_mode": Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
                "price_min": 0,
                "price_max": 0,
                "duration": 0,
                "groups": [
                    single_group(
                        "Rodzaj problemu",
                        [
                            ("Problem ze sprzętem", 0, 0, 0, 1),
                            ("Problem z systemem lub programami", 0, 0, 0, 2),
                            ("Nie wiem - proszę o diagnozę", 0, 0, 0, 3),
                        ],
                        required=False,
                    )
                ],
            },
        ]

        desired_names = {service_data["name"] for service_data in services}
        legacy_names = {
            "Czyszczenie laptopa",
            "Diagnostyka komputera",
            "Instalacja systemu operacyjnego",
            "Wymiana dysku na SSD",
            *rename_existing_services.keys(),
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
