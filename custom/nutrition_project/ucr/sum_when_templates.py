from corehq.apps.userreports.reports.sum_when_templates import (
    SumWhenTemplateSpec,
)
from corehq.apps.userreports.specs import TypeProperty


class ChildDeliverySpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_child_delivery")
    expression = "gender = ? AND residential_status = ? AND child_safe_and_alive = ?"


class ChildWeighedSpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_child_weighed")
    expression = "gender = ? AND residential_status = ? AND child_safe_and_alive = 'yes' AND weight is NOT NULL"


class ChildLowBirthWeightSpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_child_low_birth_weight")
    expression = "gender = ? AND residential_status = ? AND child_safe_and_alive = 'yes' AND " \
                 "weight is NOT NULL AND low_birth_weight = 'yes'"


class ChildDeathSpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_child_death")
    expression = "gender = ? AND residential_status = ? AND death_date - dob BETWEEN ? AND ?"


class WomanDeathSpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_woman_death")
    expression = "gender = 'F' AND residential_status = ? AND age_at_death_yrs >= ?"


class WomanDeathTypeSpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_woman_death_type")
    expression = "gender = 'F' AND residential_status = ? AND female_death_type = ?"


class GenderAndResidentTypeSpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_gender_and_resident_type")
    expression = "gender = ? AND residential_status = ?"


class NutritionCenterOpenTodaySpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_nutrition_center_open_today")
    expression = "nutrition_center_open_today = ?"


class OnTimeVisitCheckSpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_on_time_visit_check")
    expression = "on_time_visit_check = ?"


class BreastfeedingSpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_breastfeeding")
    expression = "breastfeeding = ?"


class ImmediateBreastfeedingInitiatedSpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_immediate_breastfeeding_initiated")
    expression = "immediate_breastfeeding_initiated = ?"


class ComplementaryFeedingStartedCheckSpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_cf_started_check")
    expression = "cf_started_check = ?"


class LatestBMICategorySpec(SumWhenTemplateSpec):
    type = TypeProperty("india-nutrition-project_latest_bmi_category")
    expression = "latest_bmi_category = ?"
