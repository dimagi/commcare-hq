from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0007_property_type_choices'),
        ('fhir', '0005_fhirimportconfig'),
    ]

    operations = [
        migrations.CreateModel(
            name='FHIRImportResourceType',
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
                ('import_config', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='resource_types',
                    to='fhir.FHIRImportConfig',
                )),
            ],
        ),
        migrations.CreateModel(
            name='ResourceTypeRelationship',
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
                    to='fhir.FHIRImportResourceType',
                )),
                ('resource_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='jsonpaths_to_related_resource_types',
                    to='fhir.FHIRImportResourceType',
                )),
            ],
        ),
    ]
