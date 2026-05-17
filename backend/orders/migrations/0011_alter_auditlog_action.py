from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0010_serviceorder_customer_accepted_repair_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[('STATUS_CHANGED', 'Zmiana statusu'), ('COMMENT_ADDED', 'Dodanie komentarza'), ('ESTIMATE_SET', 'Ustawienie estymacji'), ('ORDER_CANCELED', 'Anulowanie zlecenia'), ('ORDER_CREATED', 'Utworzenie zlecenia'), ('DIAGNOSIS_UPDATED', 'Aktualizacja diagnozy'), ('REPAIR_ACCEPTED', 'Akceptacja naprawy')], db_index=True, max_length=50),
        ),
    ]
