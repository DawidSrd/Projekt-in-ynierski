import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0011_alter_auditlog_action'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='serviceorder',
            name='assigned_technician',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_service_orders', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[('STATUS_CHANGED', 'Zmiana statusu'), ('COMMENT_ADDED', 'Dodanie komentarza'), ('ESTIMATE_SET', 'Ustawienie estymacji'), ('ORDER_CANCELED', 'Anulowanie zlecenia'), ('ORDER_CREATED', 'Utworzenie zlecenia'), ('DIAGNOSIS_UPDATED', 'Aktualizacja diagnozy'), ('REPAIR_ACCEPTED', 'Akceptacja naprawy'), ('TECHNICIAN_ASSIGNED', 'Przypisanie technika')], db_index=True, max_length=50),
        ),
    ]
