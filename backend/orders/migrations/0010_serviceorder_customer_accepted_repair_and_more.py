from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0009_serviceorder_device_brand_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='serviceorder',
            name='customer_accepted_repair',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='serviceorder',
            name='diagnosis',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='serviceorder',
            name='final_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='serviceorder',
            name='repair_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[('STATUS_CHANGED', 'Zmiana statusu'), ('COMMENT_ADDED', 'Dodanie komentarza'), ('ESTIMATE_SET', 'Ustawienie estymacji'), ('ORDER_CANCELED', 'Anulowanie zlecenia'), ('ORDER_CREATED', 'Utworzenie zlecenia'), ('DIAGNOSIS_UPDATED', 'Aktualizacja diagnozy')], db_index=True, max_length=50),
        ),
    ]
