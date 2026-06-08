from django.db import migrations, models


def assign_catalog_positions(apps, schema_editor):
    Service = apps.get_model("orders", "Service")
    for position, service in enumerate(Service.objects.order_by("id"), start=1):
        service.catalog_position = position
        service.save(update_fields=["catalog_position"])


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0019_simplify_option_admin_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="catalog_position",
            field=models.PositiveIntegerField(default=999),
        ),
        migrations.RunPython(assign_catalog_positions, migrations.RunPython.noop),
    ]
