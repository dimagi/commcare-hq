from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0006_add_sql_case_repeater'),
    ]

    operations = [
        migrations.CreateModel(
            name='SQLCreateCaseRepeater',
            fields=[
                ('sqlcaserepeater_ptr', models.OneToOneField(
                    auto_created=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    parent_link=True,
                    primary_key=True,
                    serialize=False,
                    to='repeaters.SQLCaseRepeater',
                )),
            ],
            options={
                'db_table': 'repeaters_createcaserepeater',
            },
            bases=('repeaters.sqlcaserepeater',),
        ),
    ]
