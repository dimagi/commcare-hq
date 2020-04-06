import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AutomaticUpdateRule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=126, db_index=True)),
                ('name', models.CharField(max_length=126)),
                ('case_type', models.CharField(max_length=126)),
                ('active', models.BooleanField(default=False)),
                ('deleted', models.BooleanField(default=False)),
                ('last_run', models.DateTimeField(null=True)),
                ('server_modified_boundary', models.IntegerField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AutomaticUpdateAction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('action', models.CharField(max_length=10, choices=[('UPDATE', 'UPDATE'), ('CLOSE', 'CLOSE')])),
                ('property_name', models.CharField(max_length=126, null=True)),
                ('property_value', models.CharField(max_length=126, null=True)),
                ('rule', models.ForeignKey(to='data_interfaces.AutomaticUpdateRule', on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AutomaticUpdateRuleCriteria',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('property_name', models.CharField(max_length=126)),
                ('property_value', models.CharField(max_length=126, null=True)),
                ('match_type', models.CharField(max_length=10, choices=[('DAYS', 'DAYS'), ('EQUAL', 'EQUAL'), ('NOT_EQUAL', 'NOT_EQUAL'), ('EXISTS', 'EXISTS')])),
                ('rule', models.ForeignKey(to='data_interfaces.AutomaticUpdateRule', on_delete=django.db.models.deletion.PROTECT)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
