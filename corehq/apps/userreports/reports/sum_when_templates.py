import re

from dimagi.ext.jsonobject import (
    IntegerProperty,
    JsonObject,
    ListProperty,
    StringProperty,
)

from corehq.apps.userreports.specs import TypeProperty


class SumWhenTemplateSpec(JsonObject):
    type = StringProperty(required=True)
    expression = StringProperty(required=True)
    binds = ListProperty()
    then = IntegerProperty()

    def bind_count(self):
        return len(re.sub(r'[^?]', '', self.expression))


### Templates for testing

class YearRangeTemplateSpec(SumWhenTemplateSpec):
    type = TypeProperty('year_range')
    expression = "year >= ? and year < ?"


class UnderXMonthsTemplateSpec(SumWhenTemplateSpec):
    type = TypeProperty("under_x_months")
    expression = "age_at_registration < ?"


### Templates for ICDS

class AdultFemaleMigrantDeathSpec(SumWhenTemplateSpec):
    type = TypeProperty("adult_female_migrant_death")
    expression = "sex = 'F' AND resident IS DISTINCT FROM 1 AND age_at_death_yrs >= 11"


class AdultFemaleResidentDeathSpec(SumWhenTemplateSpec):
    type = TypeProperty("adult_female_resident_death")
    expression = "sex = 'F' AND resident = 1 AND age_at_death_yrs >= 11"


class AgeAtDeathRangeMigrantSpec(SumWhenTemplateSpec):
    type = TypeProperty("age_at_death_range_migrant")
    expression = "sex = ? AND resident IS DISTINCT FROM 1 AND date_death - dob BETWEEN ? AND ?"


class AgeAtDeathRangeResidentSpec(SumWhenTemplateSpec):
    type = TypeProperty("age_at_death_range_resident")
    expression = "sex = ? AND resident = 1 AND date_death - dob BETWEEN ? AND ?"


class CCSPhaseNullTemplateSpec(SumWhenTemplateSpec):
    type = TypeProperty("ccs_phase_null")
    expression = "ccs_phase IS NULL"


class CCSPhaseTemplateSpec(SumWhenTemplateSpec):
    type = TypeProperty("ccs_phase")
    expression = "ccs_phase = ?"


class ComplementaryFeedingTemplateSpec(SumWhenTemplateSpec):
    type = TypeProperty("complementary_feeding")
    expression = "is_cf = ?"


class ClosedOnNullTemplateSpec(SumWhenTemplateSpec):
    type = TypeProperty("closed_on_null")
    expression = "closed_on IS NULL"


class FemaleAgeAtDeathSpec(SumWhenTemplateSpec):
    type = TypeProperty("female_age_at_death")
    expression = "female_death_type IS NOT NULL AND female_death_type != '' AND age_at_death_yrs >= ?"


class FemaleDeathTypeMigrantSpec(SumWhenTemplateSpec):
    type = TypeProperty("female_death_type_migrant")
    expression = "female_death_type = ? AND resident IS DISTINCT FROM 1"


class FemaleDeathTypeResidentSpec(SumWhenTemplateSpec):
    type = TypeProperty("female_death_type_resident")
    expression = "female_death_type = ? AND resident = 1"


class OpenDisabilityTypeSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_disability_type")
    expression = "closed_on IS NULL AND disability_type ~ ?"


class OpenFemaleSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female")
    expression = "closed_on IS NULL AND sex = 'F'"


class OpenFemaleDisabledSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_disabled")
    expression = "closed_on IS NULL AND sex = 'F' and disabled = 1"


class OpenFemaleHHCasteSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_hh_caste")
    expression = "closed_on IS NULL AND sex = 'F' and hh_caste = ?"


class OpenFemaleHHCasteNotSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_hh_caste_not")
    expression = "closed_on IS NULL AND sex = 'F' and hh_caste NOT IN (?, ?)"


class OpenFemaleHHMinoritySpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_hh_minority")
    expression = "closed_on IS NULL AND sex = 'F' and hh_minority = 1"


class OpenFemaleMigrantSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_migrant")
    expression = "closed_on IS NULL AND sex = 'F' AND resident != 1"


class OpenFemaleMigrantDistinctFromSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_migrant_distinct_from")
    expression = "closed_on IS NULL AND sex = 'F' AND resident IS DISTINCT FROM 1"


class OpenFemaleResidentSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_resident")
    expression = "closed_on IS NULL AND sex = 'F' AND resident = 1"


class OpenMaleDisabledSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_male_disabled")
    expression = "closed_on IS NULL AND sex IN ('M', 'O') and disabled = 1"


class OpenMaleHHCasteSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_male_hh_caste")
    expression = "closed_on IS NULL AND sex IN ('M', 'O') and hh_caste = ?"


class OpenMaleHHCasteNotSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_male_hh_caste_not")
    expression = "closed_on IS NULL AND sex in ('M', 'O') and hh_caste NOT IN (?, ?)"


class OpenMaleHHMinoritySpec(SumWhenTemplateSpec):
    type = TypeProperty("open_male_hh_minority")
    expression = "closed_on IS NULL AND sex in ('M', 'O') and hh_minority = 1"


class OpenMaleMigrantSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_male_migrant")
    expression = "closed_on IS NULL AND sex IN ('M', 'O') AND resident != 1"


class OpenMaleMigrantDistinctFromSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_male_migrant_distinct_from")
    expression = "closed_on IS NULL AND sex IN ('M', 'O') AND resident IS DISTINCT FROM 1"


class OpenMaleResidentSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_male_resident")
    expression = "closed_on IS NULL AND sex IN ('M', 'O') AND resident = 1"


class OpenPregnantMigrantSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_pregnant_migrant")
    expression = "closed_on IS NULL AND is_pregnant = 1 and sex = 'F' AND resident != 1"


class OpenPregnantResidentSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_pregnant_resident")
    expression = "closed_on IS NULL AND is_pregnant = 1 and sex = 'F' AND resident = 1"


class ReachedReferralHealthProblemSpec(SumWhenTemplateSpec):
    type = TypeProperty("reached_referral_health_problem")
    expression = "referral_reached_facility = ? AND referral_health_problem ~ ?"


class ReachedReferralHealthProblem2ProblemsSpec(SumWhenTemplateSpec):
    type = TypeProperty("reached_referral_health_problem_2_problems")
    expression = "referral_reached_facility = ? AND (referral_health_problem ~ ? OR referral_health_problem ~ ?)"


class ReachedReferralHealthProblem3ProblemsSpec(SumWhenTemplateSpec):
    type = TypeProperty("reached_referral_health_problem_3_problems")
    expression = "referral_reached_facility = ? AND (referral_health_problem ~ ? OR referral_health_problem ~ ? OR referral_health_problem ~ ?)"


class ReachedReferralHealthProblem5ProblemsSpec(SumWhenTemplateSpec):
    type = TypeProperty("reached_referral_health_problem_5_problems")
    expression = "referral_reached_facility = ? AND (referral_health_problem ~ ? OR referral_health_problem ~ ? OR referral_health_problem ~ ? OR referral_health_problem ~ ? OR referral_health_problem ~ ?)"


class ReferralHealthProblemSpec(SumWhenTemplateSpec):
    type = TypeProperty("referral_health_problem")
    expression = "referral_health_problem ~ ?"


class ReferralHealthProblem2ProblemsSpec(SumWhenTemplateSpec):
    type = TypeProperty("referral_health_problem_2_problems")
    expression = "referral_health_problem ~ ? OR referral_health_problem ~ ?"


class ReferralHealthProblem3ProblemsSpec(SumWhenTemplateSpec):
    type = TypeProperty("referral_health_problem_3_problems")
    expression = "referral_health_problem ~ ? OR referral_health_problem ~ ? OR referral_health_problem ~ ?"


class ReferralHealthProblem5ProblemsSpec(SumWhenTemplateSpec):
    type = TypeProperty("referral_health_problem_5_problems")
    expression = "referral_health_problem ~ ? OR referral_health_problem ~ ? OR referral_health_problem ~ ? OR referral_health_problem ~ ? OR referral_health_problem ~ ?"
