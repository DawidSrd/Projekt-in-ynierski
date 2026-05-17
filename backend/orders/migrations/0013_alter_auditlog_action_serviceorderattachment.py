import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0012_serviceorder_assigned_technician_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[('STATUS_CHANGED', 'Zmiana statusu'), ('COMMENT_ADDED', 'Dodanie komentarza'), ('ESTIMATE_SET', 'Ustawienie estymacji'), ('ORDER_CANCELED', 'Anulowanie zlecenia'), ('ORDER_CREATED', 'Utworzenie zlecenia'), ('DIAGNOSIS_UPDATED', 'Aktualizacja diagnozy'), ('REPAIR_ACCEPTED', 'Akceptacja naprawy'), ('TECHNICIAN_ASSIGNED', 'Przypisanie technika'), ('ATTACHMENT_ADDED', 'Dodanie załącznika')], db_index=True, max_length=50),
        ),
        migrations.CreateModel(
            name='ServiceOrderAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visibility', models.CharField(choices=[('INTERNAL', 'Wewnętrzny'), ('PUBLIC', 'Publiczny')], db_index=True, default='INTERNAL', max_length=20)),
                ('file', models.FileField(upload_to='order_attachments/%Y/%m/')),
                ('original_name', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='orders.serviceorder')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='service_order_attachments', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
