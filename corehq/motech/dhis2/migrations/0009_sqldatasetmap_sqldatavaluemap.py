from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0006_connection_settings'),
        ('dhis2', '0008_rename_sqldhis2connection'),
    ]

    operations = [
        migrations.CreateModel(
            name='SQLDataSetMap',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('couch_id', models.CharField(
                    db_index=True,
                    max_length=36,
                    blank=True,
                    null=True,
                )),
                ('ucr_id', models.CharField(max_length=36)),
                ('description', models.TextField()),
                ('frequency', models.CharField(
                    max_length=16,
                    choices=[
                        ('weekly', 'Weekly'),
                        ('monthly', 'Monthly'),
                        ('quarterly', 'Quarterly')
                    ],
                    default='monthly',
                )),
                ('day_to_send', models.PositiveIntegerField()),
                ('data_set_id', models.CharField(
                    max_length=11,
                    blank=True,
                    null=True,
                )),
                ('org_unit_id', models.CharField(
                    max_length=11,
                    blank=True,
                    null=True,
                )),
                ('org_unit_column', models.CharField(
                    max_length=64,
                    blank=True,
                    null=True,
                )),
                ('period', models.CharField(
                    max_length=32,
                    blank=True,
                    null=True,
                )),
                ('period_column', models.CharField(
                    max_length=64,
                    blank=True,
                    null=True,
                )),
                ('attribute_option_combo_id', models.CharField(
                    max_length=11,
                    blank=True,
                    null=True,
                )),
                ('complete_date', models.DateField(blank=True, null=True)),
                ('connection_settings', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to='motech.ConnectionSettings',
                    blank=True,
                    null=True,
                )),
            ],
        ),
        migrations.CreateModel(
            name='SQLDataValueMap',
            fields=[
                ('id', models.AutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('column', models.CharField(max_length=64)),
                ('data_element_id', models.CharField(max_length=11)),
                ('category_option_combo_id', models.CharField(
                    max_length=11,
                    blank=True,
                )),
                ('comment', models.TextField(blank=True, null=True)),
                ('dataset_map', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='datavalue_maps',
                    to='dhis2.SQLDataSetMap',
                )),
            ],
        ),
    ]
