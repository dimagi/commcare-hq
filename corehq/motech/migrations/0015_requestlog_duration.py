# Generated by Django 4.2.14 on 2024-08-17 18:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("motech", "0014_alter_connectionsettings_password"),
    ]

    operations = [
        migrations.AddField(
            model_name="requestlog",
            name="duration",
            field=models.IntegerField(null=True),
        ),
    ]
