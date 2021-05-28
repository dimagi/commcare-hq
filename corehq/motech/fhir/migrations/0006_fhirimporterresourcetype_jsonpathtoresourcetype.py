from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0007_property_type_choices'),
        ('fhir', '0005_fhirimporter'),
    ]

    operations = [
        migrations.CreateModel(
            name='FHIRImporterResourceType',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('name', models.CharField(max_length=255)),
                ('import_related_only', models.BooleanField(default=False)),
                ('search_params', jsonfield.fields.JSONField(default=dict)),
                ('case_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='data_dictionary.CaseType',
                )),
                ('fhir_importer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='resource_types',
                    to='fhir.FHIRImporter',
                )),
            ],
        ),
        migrations.CreateModel(
            name='JSONPathToResourceType',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('jsonpath', models.TextField(default='')),
                ('related_resource_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='fhir.FHIRImporterResourceType',
                )),
                ('resource_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='jsonpaths_to_related_resource_types',
                    to='fhir.FHIRImporterResourceType',
                )),
            ],
        ),
    ]
