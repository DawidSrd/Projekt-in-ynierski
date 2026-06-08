from django.db import migrations, models


def mark_featured_service(apps, schema_editor):
    Service = apps.get_model("orders", "Service")
    service = Service.objects.filter(
        name__iexact="Inne / indywidualna diagnoza",
        is_active=True,
    ).first()
    if service:
        service.is_featured = True
        service.save(update_fields=["is_featured"])


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0020_service_catalog_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="is_featured",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_featured_service, migrations.RunPython.noop),
    ]
