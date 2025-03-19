from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('campaign', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name="DashboardMap",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("display_order", models.IntegerField(default=0)),
                ("case_type", models.CharField(max_length=255)),
                ("geo_case_property", models.CharField(max_length=255)),
                (
                    "dashboard",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="maps",
                        to="campaign.dashboard",
                    ),
                ),
            ],
            options={
                "ordering": ["display_order"],
            },
        ),
        migrations.CreateModel(
            name="DashboardReport",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("display_order", models.IntegerField(default=0)),
                ("report_configuration_id", models.CharField(max_length=36)),
                (
                    "dashboard",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reports",
                        to="campaign.dashboard",
                    ),
                ),
            ],
            options={
                "ordering": ["display_order"],
            },
        ),
    ]
