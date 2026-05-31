from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0018_simplify_offer_admin_names"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="serviceoption",
            options={"verbose_name": "wariant opcji", "verbose_name_plural": "Warianty opcji"},
        ),
        migrations.AlterModelOptions(
            name="serviceoptiongroup",
            options={"verbose_name": "opcja usługi", "verbose_name_plural": "Opcje usług"},
        ),
    ]
