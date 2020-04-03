from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='automaticupdaterulecriteria',
            name='match_type',
            field=models.CharField(max_length=10, choices=[('DAYS', 'DAYS'), ('EQUAL', 'EQUAL'), ('NOT_EQUAL', 'NOT_EQUAL')]),
            preserve_default=True,
        ),
    ]
