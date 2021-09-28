from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('fhir', '0007_fhirimportresourceproperty'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fhirimportresourcetype',
            name='search_params',
            field=jsonfield.fields.JSONField(blank=True, default=dict),
        ),
    ]
