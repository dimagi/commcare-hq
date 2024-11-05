# Generated by Django 4.2.15 on 2024-10-18 06:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0073_rm_location_from_user_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="connectiduserlink",
            name="channel_id",
            field=models.CharField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="connectiduserlink",
            name="messaging_consent",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='connectiduserlink',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="ConnectIDMessagingKey",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("domain", models.TextField()),
                ("key", models.CharField(blank=True, max_length=44, null=True)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("active", models.BooleanField(default=True)),
                (
                    "connectid_user_link",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="users.connectiduserlink",
                    ),
                ),
            ],
        ),
    ]
