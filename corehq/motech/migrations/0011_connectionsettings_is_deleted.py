# Generated by Django 2.2.27 on 2022-04-05 05:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0010_auto_20211124_1931'),
    ]

    operations = [
        migrations.AddField(
            model_name='connectionsettings',
            name='is_deleted',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
