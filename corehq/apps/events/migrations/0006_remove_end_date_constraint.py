# Generated by Django 3.2.16 on 2023-04-03 08:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0005_rename_alter_event__attendance_taker_ids'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='end_date',
            field=models.DateField(null=True),
        ),
    ]
