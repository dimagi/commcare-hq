# Generated by Django 2.2.13 on 2020-07-27 11:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0019_editreportspermissions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userreportingmetadatastaging',
            name='id',
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
    ]
