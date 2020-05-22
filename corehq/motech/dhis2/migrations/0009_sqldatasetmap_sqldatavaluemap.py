import corehq.motech.dhis2.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0005_requestlog_request_body'),
        ('dhis2', '0008_rename_sqldhis2connection'),
    ]

    operations = [
        migrations.CreateModel(
            name='SQLDataSetMap',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID',
                )),
                ('domain', models.CharField(max_length=126)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('report_config_id', models.CharField(max_length=126)),
                ('frequency', models.CharField(
                    choices=[
                        ('weekly', 'Weekly'),
                        ('monthly', 'Monthly'),
                        ('quarterly', 'Quarterly')
                    ], default='monthly', max_length=15,
                )),
                ('day_to_send', models.IntegerField()),
                ('data_set_id', models.CharField(
                    blank=True, max_length=11, null=True,
                    validators=[corehq.motech.dhis2.validators.validate_dhis2_uid],
                )),
                ('org_unit_id', models.CharField(
                    blank=True, max_length=11, null=True,
                    validators=[corehq.motech.dhis2.validators.validate_dhis2_uid],
                )),
                ('org_unit_column', models.CharField(
                    blank=True, max_length=255, null=True,
                )),
                ('period_column', models.CharField(
                    blank=True, max_length=255, null=True,
                )),
                ('attribute_option_combo_id', models.CharField(
                    blank=True, max_length=11, null=True,
                    validators=[corehq.motech.dhis2.validators.validate_dhis2_uid],
                )),
                ('complete_date', models.DateField(blank=True, null=True)),
                ('connection_settings', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    to='motech.ConnectionSettings',
                )),
            ],
        ),
        migrations.CreateModel(
            name='SQLDataValueMap',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID',
                )),
                ('column', models.CharField(max_length=255)),
                ('data_element_id', models.CharField(
                    max_length=11,
                    validators=[corehq.motech.dhis2.validators.validate_dhis2_uid],
                )),
                ('category_option_combo_id', models.CharField(
                    max_length=11,
                    validators=[corehq.motech.dhis2.validators.validate_dhis2_uid],
                )),
                ('comment', models.CharField(
                    blank=True, max_length=255, null=True,
                )),
                ('dataset_map', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='dhis2.SQLDataSetMap',
                )),
            ],
        ),
    ]
