from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0002_remove_exists_option'),
    ]

    operations = [
        migrations.AlterField(
            model_name='automaticupdaterulecriteria',
            name='match_type',
            field=models.CharField(max_length=10, choices=[('DAYS', 'DAYS'), ('EQUAL', 'EQUAL'), ('NOT_EQUAL', 'NOT_EQUAL'), ('HAS_VALUE', 'HAS_VALUE')]),
            preserve_default=True,
        ),
    ]
