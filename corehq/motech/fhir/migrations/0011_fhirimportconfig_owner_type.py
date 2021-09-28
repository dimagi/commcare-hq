from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fhir', '0010_fhirimportconfig_frequency_choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='fhirimportconfig',
            name='owner_type',
            field=models.CharField(
                choices=[
                    ('group', 'Group'),
                    ('location', 'Location'),
                    ('user', 'User'),
                ],
                default='user',
                max_length=12,
            ),
            preserve_default=False,
        ),
    ]
