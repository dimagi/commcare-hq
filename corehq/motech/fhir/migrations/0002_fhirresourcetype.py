from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0007_property_type_choices'),
        ('fhir', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fhirresourcetype',
            name='template',
            field=jsonfield.fields.JSONField(default=dict),
        ),
        migrations.AlterUniqueTogether(
            name='fhirresourcetype',
            unique_together={('case_type', 'fhir_version')},
        ),
    ]
