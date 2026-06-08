from django.core.management.base import BaseCommand

from orders.models import Service, ServiceOption, ServiceOptionGroup


SERVICES = [
    {
        "name": "Czyszczenie i konserwacja laptopa/PC",
        "description": "Dla urządzeń, które się grzeją, głośno pracują albo dawno nie były czyszczone.",
        "price_min": 120,
        "price_max": 220,
        "duration": 90,
        "position": 1,
        "groups": [
            {
                "name": "Zakres czyszczenia",
                "type": ServiceOptionGroup.SelectionType.SINGLE,
                "required": True,
                "options": [
                    ("Standardowe czyszczenie", 0, 0, 0),
                    ("Pełna konserwacja z wymianą pasty", 40, 70, 20),
                ],
            },
        ],
    },
    {
        "name": "Instalacja systemu Windows",
        "description": "Instalacja systemu, sterowników i podstawowa konfiguracja komputera do pracy.",
        "price_min": 140,
        "price_max": 260,
        "duration": 120,
        "position": 2,
        "groups": [
            {
                "name": "Rodzaj instalacji",
                "type": ServiceOptionGroup.SelectionType.SINGLE,
                "required": True,
                "options": [
                    ("Instalacja na czysto", 0, 0, 0),
                    ("Reinstalacja z zachowaniem danych", 80, 140, 60),
                ],
            },
        ],
    },
    {
        "name": "Inne / indywidualna diagnoza",
        "description": "Opisz objawy, a serwis określi możliwy zakres prac po sprawdzeniu sprzętu.",
        "price_min": 0,
        "price_max": 0,
        "duration": 0,
        "position": 3,
        "pricing_mode": Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
        "is_featured": True,
        "groups": [],
    },
]


class Command(BaseCommand):
    help = "Dodaje trzy przykładowe usługi do pustego katalogu."

    def handle(self, *args, **options):
        created_services = 0

        for service_data in SERVICES:
            service, created = Service.objects.get_or_create(
                name=service_data["name"],
                defaults={
                    "description": service_data["description"],
                    "pricing_mode": service_data.get(
                        "pricing_mode",
                        Service.PricingMode.CONFIGURABLE,
                    ),
                    "base_price_min": service_data["price_min"],
                    "base_price_max": service_data["price_max"],
                    "base_duration_minutes": service_data["duration"],
                    "catalog_position": service_data["position"],
                    "is_active": True,
                    "is_featured": service_data.get("is_featured", False),
                },
            )
            created_services += int(created)

            for group_position, group_data in enumerate(service_data["groups"], start=1):
                group, _ = ServiceOptionGroup.objects.get_or_create(
                    service=service,
                    name=group_data["name"],
                    defaults={
                        "selection_type": group_data["type"],
                        "is_required": group_data["required"],
                        "sort_order": group_position * 10,
                        "is_active": True,
                    },
                )

                for option_position, option_data in enumerate(
                    group_data["options"],
                    start=1,
                ):
                    name, price_min, price_max, duration = option_data
                    ServiceOption.objects.get_or_create(
                        group=group,
                        name=name,
                        defaults={
                            "price_delta_min": price_min,
                            "price_delta_max": price_max,
                            "duration_delta_minutes": duration,
                            "sort_order": option_position * 10,
                            "is_active": True,
                        },
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Gotowe: dodano {created_services} z 3 przykładowych usług."
            )
        )
