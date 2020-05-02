import json

from django.conf import settings
from django.utils.translation import ugettext as _

from jsonobject.exceptions import BadValueError

from corehq.apps.userreports.const import AGGGREGATION_TYPE_ARRAY_AGG_LAST_VALUE
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.reports.specs import (
    AgeInMonthsBucketsColumn,
    AggregateDateColumn,
    ExpandedColumn,
    ExpressionColumn,
    FieldColumn,
    IntegerBucketsColumn,
    LocationColumn,
    MultibarAggregateChartSpec,
    MultibarChartSpec,
    OrderBySpec,
    PercentageColumn,
    PieChartSpec,
    SumWhenColumn,
    SumWhenTemplateColumn,
    ArrayAggLastValueReportColumn,
)
from corehq.apps.userreports.reports.sum_when_templates import (
    AdultFemaleMigrantDeathSpec,
    AdultFemaleResidentDeathSpec,
    AgeAtDeathRangeMigrantSpec,
    AgeAtDeathRangeResidentSpec,
    CCSPhaseNullTemplateSpec,
    CCSPhaseTemplateSpec,
    ComplementaryFeedingTemplateSpec,
    ClosedOnNullTemplateSpec,
    FemaleAgeAtDeathSpec,
    FemaleDeathTypeMigrantSpec,
    FemaleDeathTypeResidentSpec,
    OpenDisabilityTypeSpec,
    OpenFemaleSpec,
    OpenFemaleDisabledSpec,
    OpenFemaleHHCasteSpec,
    OpenFemaleHHCasteNotSpec,
    OpenFemaleHHMinoritySpec,
    OpenFemaleMigrantSpec,
    OpenFemaleMigrantDistinctFromSpec,
    OpenFemaleResidentSpec,
    OpenMaleDisabledSpec,
    OpenMaleHHCasteSpec,
    OpenMaleHHCasteNotSpec,
    OpenMaleHHMinoritySpec,
    OpenMaleMigrantSpec,
    OpenMaleMigrantDistinctFromSpec,
    OpenMaleResidentSpec,
    OpenPregnantMigrantSpec,
    OpenPregnantResidentSpec,
    ReachedReferralHealthProblemSpec,
    ReachedReferralHealthProblem2ProblemsSpec,
    ReachedReferralHealthProblem3ProblemsSpec,
    ReachedReferralHealthProblem5ProblemsSpec,
    ReferralHealthProblemSpec,
    ReferralHealthProblem2ProblemsSpec,
    ReferralHealthProblem3ProblemsSpec,
    ReferralHealthProblem5ProblemsSpec,
    UnderXMonthsTemplateSpec,
    YearRangeTemplateSpec,
)


class ReportColumnFactory(object):
    class_map = {
        'age_in_months_buckets': AgeInMonthsBucketsColumn,
        'aggregate_date': AggregateDateColumn,
        'expanded': ExpandedColumn,
        'expression': ExpressionColumn,
        'field': FieldColumn,
        'integer_buckets': IntegerBucketsColumn,
        'location': LocationColumn,
        'percent': PercentageColumn,
        'sum_when': SumWhenColumn,
        'sum_when_template': SumWhenTemplateColumn,
        AGGGREGATION_TYPE_ARRAY_AGG_LAST_VALUE: ArrayAggLastValueReportColumn,
    }

    @classmethod
    def from_spec(cls, spec, is_static, domain=None):
        column_type = spec.get('type') or 'field'
        if column_type not in cls.class_map:
            raise BadSpecError(
                'Unknown or missing column type: {} must be in [{}]'.format(
                    column_type,
                    ', '.join(cls.class_map)
                )
            )
        column_class = cls.class_map[column_type]
        if column_class.restricted_to_static(domain) and not (is_static or settings.UNIT_TESTING):
            raise BadSpecError("{} columns are only available to static report configs"
                               .format(column_type))
        try:
            return column_class.wrap(spec)
        except BadValueError as e:
            raise BadSpecError(_(
                'Problem creating column from spec: {}, message is: {}'
            ).format(
                json.dumps(spec, indent=2),
                str(e),
            ))


class ChartFactory(object):
    spec_map = {
        'pie': PieChartSpec,
        'multibar': MultibarChartSpec,
        'multibar-aggregate': MultibarAggregateChartSpec,
    }

    @classmethod
    def from_spec(cls, spec):
        if spec.get('type') not in cls.spec_map:
            raise BadSpecError(_('Illegal chart type: {0}, must be one of the following choices: ({1})').format(
                spec.get('type', _('(missing from spec)')),
                ', '.join(cls.spec_map)
            ))
        try:
            return cls.spec_map[spec['type']].wrap(spec)
        except BadValueError as e:
            raise BadSpecError(_('Problem creating chart from spec: {}, message is: {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))


class ReportOrderByFactory(object):

    @classmethod
    def from_spec(cls, spec):
        return OrderBySpec.wrap(spec)


class SumWhenTemplateFactory(object):
    spec_map = {
        'adult_female_migrant_death': AdultFemaleMigrantDeathSpec,
        'adult_female_resident_death': AdultFemaleResidentDeathSpec,
        'age_at_death_range_migrant': AgeAtDeathRangeMigrantSpec,
        'age_at_death_range_resident': AgeAtDeathRangeResidentSpec,
        'ccs_phase': CCSPhaseTemplateSpec,
        'ccs_phase_null': CCSPhaseNullTemplateSpec,
        'complementary_feeding': ComplementaryFeedingTemplateSpec,
        'closed_on_null': ClosedOnNullTemplateSpec,
        'female_age_at_death': FemaleAgeAtDeathSpec,
        'female_death_type_migrant': FemaleDeathTypeMigrantSpec,
        'female_death_type_resident': FemaleDeathTypeResidentSpec,
        'open_disability_type': OpenDisabilityTypeSpec,
        'open_female': OpenFemaleSpec,
        'open_female_disabled': OpenFemaleDisabledSpec,
        'open_female_hh_caste': OpenFemaleHHCasteSpec,
        'open_female_hh_caste_not': OpenFemaleHHCasteNotSpec,
        'open_female_hh_minority': OpenFemaleHHMinoritySpec,
        'open_female_migrant': OpenFemaleMigrantSpec,
        'open_female_migrant_distinct_from': OpenFemaleMigrantDistinctFromSpec,
        'open_female_resident': OpenFemaleResidentSpec,
        'open_male_disabled': OpenMaleDisabledSpec,
        'open_male_hh_caste': OpenMaleHHCasteSpec,
        'open_male_hh_caste_not': OpenMaleHHCasteNotSpec,
        'open_male_hh_minority': OpenMaleHHMinoritySpec,
        'open_male_migrant': OpenMaleMigrantSpec,
        'open_male_migrant_distinct_from': OpenMaleMigrantDistinctFromSpec,
        'open_male_resident': OpenMaleResidentSpec,
        'open_pregnant_migrant': OpenPregnantMigrantSpec,
        'open_pregnant_resident': OpenPregnantResidentSpec,
        'reached_referral_health_problem': ReachedReferralHealthProblemSpec,
        'reached_referral_health_problem_2_problems': ReachedReferralHealthProblem2ProblemsSpec,
        'reached_referral_health_problem_3_problems': ReachedReferralHealthProblem3ProblemsSpec,
        'reached_referral_health_problem_5_problems': ReachedReferralHealthProblem5ProblemsSpec,
        'referral_health_problem': ReferralHealthProblemSpec,
        'referral_health_problem_2_problems': ReferralHealthProblem2ProblemsSpec,
        'referral_health_problem_3_problems': ReferralHealthProblem3ProblemsSpec,
        'referral_health_problem_5_problems': ReferralHealthProblem5ProblemsSpec,
        'under_x_months': UnderXMonthsTemplateSpec,
        'year_range': YearRangeTemplateSpec,
    }

    @classmethod
    def make_template(cls, spec):
        if spec.get('type') not in cls.spec_map:
            raise BadSpecError(_('Illegal sum_when_template type: "{0}", must be in: ({1})').format(
                spec.get('type'),
                ', '.join(cls.spec_map)
            ))
        try:
            template = cls.spec_map[spec['type']].wrap(spec)
        except BadValueError as e:
            raise BadSpecError(_('Problem creating template: {}, message is: {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))

        expected = template.bind_count()
        actual = len(template.binds)
        if expected != actual:
            raise BadSpecError(_('Expected {} binds in sum_when_template {}, found {}').format(
                expected,
                spec['type'],
                actual
            ))

        return template
