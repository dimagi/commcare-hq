from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('fhir', '0007_fhirimporterresourceproperty'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fhirimporterresourcetype',
            name='search_params',
            field=jsonfield.fields.JSONField(blank=True, default=dict),
        ),
    ]
