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
                "name": "Czyszczenie laptopa",
                "description": (
                    "Czyszczenie układu chłodzenia, wymiana pasty "
                    "termoprzewodzącej i kontrola temperatur."
                ),
                "price_min": 120,
                "price_max": 180,
                "duration": 90,
                "groups": [
                    {
                        "name": "Pasta termoprzewodząca",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": True,
                        "sort": 1,
                        "options": [
                            ("Standardowa pasta", 0, 0, 0, 1),
                            ("Pasta premium", 30, 50, 10, 2),
                        ],
                    },
                    {
                        "name": "Tryb realizacji",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": False,
                        "sort": 2,
                        "options": [
                            ("Standardowy", 0, 0, 0, 1),
                            ("Ekspres", 70, 120, -30, 2),
                        ],
                    },
                    {
                        "name": "Dodatkowe czynności",
                        "type": ServiceOptionGroup.SelectionType.MULTI,
                        "required": False,
                        "sort": 3,
                        "options": [
                            ("Wymiana termopadów", 40, 80, 20, 1),
                            ("Pełna diagnostyka temperatur", 30, 60, 30, 2),
                        ],
                    },
                ],
            },
            {
                "name": "Diagnostyka komputera",
                "description": (
                    "Sprawdzenie podzespołów, systemu operacyjnego "
                    "i wstępna rekomendacja naprawy."
                ),
                "price_min": 80,
                "price_max": 150,
                "duration": 60,
                "groups": [
                    {
                        "name": "Zakres diagnostyki",
                        "type": ServiceOptionGroup.SelectionType.SINGLE,
                        "required": True,
                        "sort": 1,
                        "options": [
                            ("Podstawowa", 0, 0, 0, 1),
                            ("Rozszerzona z raportem", 50, 90, 30, 2),
                        ],
                    },
                ],
            },
            {
                "name": "Instalacja systemu operacyjnego",
                "description": (
                    "Instalacja systemu, sterowników i podstawowa "
                    "konfiguracja komputera."
                ),
                "price_min": 140,
                "price_max": 220,
                "duration": 120,
                "groups": [
                    {
                        "name": "Zakres konfiguracji",
                        "type": ServiceOptionGroup.SelectionType.MULTI,
                        "required": False,
                        "sort": 1,
                        "options": [
                            ("Instalacja sterowników", 0, 0, 0, 1),
                            ("Pakiet podstawowych programów", 40, 70, 30, 2),
                            ("Kopia danych użytkownika", 80, 160, 60, 3),
                        ],
                    },
                ],
            },
            {
                "name": "Wymiana dysku na SSD",
                "description": (
                    "Montaż dysku SSD oraz opcjonalne przeniesienie "
                    "danych ze starego nośnika."
                ),
                "price_min": 100,
                "price_max": 180,
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
                ],
            },
        ]

        for service_data in services:
            service, _created = Service.objects.update_or_create(
                name=service_data["name"],
                defaults={
                    "description": service_data["description"],
                    "base_price_min": money(service_data["price_min"]),
                    "base_price_max": money(service_data["price_max"]),
                    "base_duration_minutes": service_data["duration"],
                    "is_active": True,
                },
            )

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

                for option_name, delta_min, delta_max, duration_delta, sort in group_data[
                    "options"
                ]:
                    ServiceOption.objects.update_or_create(
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

        self.stdout.write(
            self.style.SUCCESS(
                "Gotowe: dodano lub zaktualizowano przykładowy katalog usług."
            )
        )
