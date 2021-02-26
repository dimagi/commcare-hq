from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('fhir', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fhirresourcetype',
            name='case_type',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                to='data_dictionary.CaseType',
            ),
        ),
        migrations.AlterField(
            model_name='fhirresourcetype',
            name='template',
            field=jsonfield.fields.JSONField(default=dict),
        ),
    ]
