from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("campaign", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DashboardMapReport",
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
                ("report_configuration_id", models.CharField(max_length=126)),
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
