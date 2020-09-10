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
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=128)),
                ('ucr_id', models.CharField(max_length=36)),
                ('description', models.TextField()),
                ('frequency', models.CharField(choices=[
                    ('weekly', 'Weekly'),
                    ('monthly', 'Monthly'),
                    ('quarterly', 'Quarterly')
                ], default='monthly', max_length=16)),
                ('day_to_send', models.PositiveIntegerField()),
                ('data_set_id', models.CharField(
                    blank=True, max_length=11, null=True)),
                ('org_unit_id', models.CharField(
                    blank=True, max_length=11, null=True)),
                ('org_unit_column', models.CharField(
                    blank=True, max_length=64, null=True)),
                ('period', models.CharField(
                    blank=True, max_length=32, null=True)),
                ('period_column', models.CharField(
                    blank=True, max_length=64, null=True)),
                ('attribute_option_combo_id', models.CharField(
                    blank=True, max_length=11, null=True)),
                ('complete_date', models.DateField(blank=True, null=True)),
                ('connection_settings', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    to='motech.ConnectionSettings')),
            ],
        ),
        migrations.CreateModel(
            name='SQLDataValueMap',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('column', models.CharField(max_length=64)),
                ('data_element_id', models.CharField(max_length=11)),
                ('category_option_combo_id', models.CharField(max_length=11)),
                ('comment', models.TextField(blank=True, null=True)),
                ('dataset_map', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='datavalue_maps', to='dhis2.SQLDataSetMap')),
            ],
        ),
    ]
