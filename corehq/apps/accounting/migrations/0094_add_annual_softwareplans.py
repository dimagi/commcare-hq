from django.db import migrations
from corehq.apps.accounting.bootstrap.config.annual_plans_may_2024 import (
    BOOTSTRAP_CONFIG,
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans


def _bootstrap_new_annual_pricing(apps, schema_editor):
    ensure_plans(BOOTSTRAP_CONFIG, verbose=True, apps=apps)


def _remove_annual_default_product_plans(apps, schema_editor):
    # annual SoftwarePlans may have already existed, so only delete the DefaultProductPlans
    DefaultProductPlan = apps.get_model('accounting', 'DefaultProductPlan')
    annual_default_product_plans = DefaultProductPlan.objects.filter(is_annual_plan=True)

    assert len(annual_default_product_plans) == 3
    annual_default_product_plans.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0093_defaultproductplan_is_annual_plan"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="defaultproductplan",
            unique_together={
                ("edition", "is_trial", "is_report_builder_enabled", "is_annual_plan")
            },
        ),
        migrations.RunPython(_bootstrap_new_annual_pricing,
                             reverse_code=_remove_annual_default_product_plans),
    ]
