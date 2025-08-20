from datetime import datetime

from django.db import migrations, models

from corehq.apps.accounting.models import SoftwarePlanVisibility

ANNUAL = "ANNUAL"


def change_plan_visibilities(apps, schema_editor):
    # one-time cleanup of existing software plans
    SoftwarePlan = apps.get_model('accounting', 'SoftwarePlan')

    enterprise_names = ["Dimagi Only CommCare Enterprise Edition"]
    enterprise_plans = SoftwarePlan.objects.filter(name__in=enterprise_names)
    enterprise_plans.update(visibility=SoftwarePlanVisibility.INTERNAL, last_modified=datetime.now())

    annual_plans = SoftwarePlan.objects.filter(visibility=ANNUAL)
    annual_plans.update(visibility=SoftwarePlanVisibility.PUBLIC, last_modified=datetime.now())


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0094_add_annual_softwareplans"),
    ]

    operations = [
        migrations.RunPython(change_plan_visibilities),
        migrations.AlterField(
            model_name="softwareplan",
            name="visibility",
            field=models.CharField(
                choices=[
                    ("PUBLIC", "PUBLIC - Anyone can subscribe"),
                    ("INTERNAL", "INTERNAL - Dimagi must create subscription"),
                    ("TRIAL", "TRIAL- This is a Trial Plan"),
                    ("ARCHIVED", "ARCHIVED - hidden from subscription change forms"),
                ],
                default="INTERNAL",
                max_length=10,
            ),
        ),
    ]
