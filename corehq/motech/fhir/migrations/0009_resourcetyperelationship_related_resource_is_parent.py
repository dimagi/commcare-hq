from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fhir', '0008_blank_search_params'),
    ]

    operations = [
        migrations.AddField(
            model_name='resourcetyperelationship',
            name='related_resource_is_parent',
            field=models.BooleanField(default=False),
        ),
    ]
