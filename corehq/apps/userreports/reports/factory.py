import json

from django.conf import settings
from django.utils.translation import ugettext as _

from jsonobject.exceptions import BadValueError

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
)
from corehq.apps.userreports.reports.sum_when_templates import (
    ClosedOnNullTemplateSpec,
    FemaleAgeAtDeathSpec,
    OpenDisabilityTypeSpec,
    OpenFemaleDisabledSpec,
    OpenFemaleHHCasteSpec,
    OpenFemaleHHCasteNotSpec,
    OpenFemaleHHMinoritySpec,
    OpenFemaleMigrantSpec,
    OpenFemaleResidentSpec,
    OpenMaleDisabledSpec,
    OpenMaleHHCasteSpec,
    OpenMaleHHCasteNotSpec,
    OpenMaleHHMinoritySpec,
    OpenMaleMigrantSpec,
    OpenMaleResidentSpec,
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
        'closed_on_null': ClosedOnNullTemplateSpec,
        'female_age_at_death': FemaleAgeAtDeathSpec,
        'open_disability_type': OpenDisabilityTypeSpec,
        'open_female_disabled': OpenFemaleDisabledSpec,
        'open_female_hh_caste': OpenFemaleHHCasteSpec,
        'open_female_hh_caste_not': OpenFemaleHHCasteNotSpec,
        'open_female_hh_minority': OpenFemaleHHMinoritySpec,
        'open_female_migrant': OpenFemaleMigrantSpec,
        'open_female_resident': OpenFemaleResidentSpec,
        'open_male_disabled': OpenMaleDisabledSpec,
        'open_male_hh_caste': OpenMaleHHCasteSpec,
        'open_male_hh_caste_noot': OpenMaleHHCasteNotSpec,
        'open_male_hh_minority': OpenMaleHHMinoritySpec,
        'open_male_migrant': OpenMaleMigrantSpec,
        'open_male_resident': OpenMaleResidentSpec,
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
            raise BadSpecError(_('Expected {} binds in sum_when_template, found {}').format(expected, actual))

        return template
