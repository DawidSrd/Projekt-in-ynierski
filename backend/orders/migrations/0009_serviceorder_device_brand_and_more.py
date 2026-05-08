from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_serviceorderitem_serviceorderitemoption'),
    ]

    operations = [
        migrations.AddField(
            model_name='serviceorder',
            name='device_brand',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='serviceorder',
            name='device_issue_description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='serviceorder',
            name='device_model',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='serviceorder',
            name='device_type',
            field=models.CharField(blank=True, choices=[('LAPTOP', 'Laptop'), ('DESKTOP', 'Komputer stacjonarny')], default='', max_length=20),
        ),
    ]
