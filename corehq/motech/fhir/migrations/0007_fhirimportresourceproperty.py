from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('fhir', '0006_fhirimportresourcetype_resourcetyperelationship'),
    ]

    operations = [
        migrations.CreateModel(
            name='FHIRImportResourceProperty',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('value_source_config', jsonfield.fields.JSONField(default=dict)),
                ('resource_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='properties',
                    to='fhir.FHIRImportResourceType',
                )),
            ],
        ),
    ]
