from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0020_tableauserver_get_reports_using_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tableauconnectedapp',
            name='encrypted_secret_value',
            field=models.CharField(max_length=128),
        )
    ]
