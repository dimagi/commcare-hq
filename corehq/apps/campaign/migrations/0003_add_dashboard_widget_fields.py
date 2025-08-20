from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("campaign", "0002_dashboardmap_dashboardreport"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="dashboardmap",
            options={"ordering": ["dashboard_tab", "display_order"]},
        ),
        migrations.AlterModelOptions(
            name="dashboardreport",
            options={"ordering": ["dashboard_tab", "display_order"]},
        ),
        migrations.AddField(
            model_name="dashboardmap",
            name="dashboard_tab",
            field=models.CharField(
                choices=[
                    ("cases", "Cases"),
                    ("mobile_workers", "Mobile Workers"),
                ],
                default="cases",
                max_length=14,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="dashboardmap",
            name="description",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dashboardmap",
            name="title",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="dashboardreport",
            name="dashboard_tab",
            field=models.CharField(
                choices=[
                    ("cases", "Cases"),
                    ("mobile_workers", "Mobile Workers"),
                ],
                default="cases",
                max_length=14,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="dashboardreport",
            name="description",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dashboardreport",
            name="title",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
