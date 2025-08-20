import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_search', '0012_casesearchconfig_sync_cases_on_form_entry'),
    ]

    operations = [
        migrations.AddField(
            model_name='casesearchconfig',
            name='fuzzy_prefix_length',
            field=models.SmallIntegerField(blank=True, null=True, validators=[
                django.core.validators.MinValueValidator(0),
                django.core.validators.MaxValueValidator(10),
            ]),
        ),
    ]
