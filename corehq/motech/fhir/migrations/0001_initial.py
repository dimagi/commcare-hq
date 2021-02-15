from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('data_dictionary', '0007_property_type_choices'),
    ]

    operations = [
        migrations.CreateModel(
            name='FHIRResourceType',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True,
                                        serialize=False,
                                        verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=127)),
                ('fhir_version', models.CharField(choices=[('4.0.1', 'R4')],
                                                  default='4.0.1',
                                                  max_length=12)),
                ('name', models.CharField(max_length=255)),
                ('template', jsonfield.fields.JSONField(
                    blank=True, default=None, null=True)),
                ('case_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='data_dictionary.CaseType')),
            ],
        ),
        migrations.CreateModel(
            name='FHIRResourceProperty',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True,
                                        serialize=False,
                                        verbose_name='ID')),
                ('jsonpath', models.TextField(
                    blank=True, default=None, null=True)),
                ('value_map', jsonfield.fields.JSONField(
                    blank=True, default=None, null=True)),
                ('value_source_config', jsonfield.fields.JSONField(
                    blank=True, default=None, null=True)),
                ('case_property', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='data_dictionary.CaseProperty',
                    blank=True, default=None, null=True)),
                ('resource_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='properties',
                    to='fhir.FHIRResourceType')),
            ],
        ),
    ]
