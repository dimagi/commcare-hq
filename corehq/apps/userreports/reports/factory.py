from __future__ import absolute_import
from __future__ import unicode_literals
import json
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from django.utils.translation import ugettext as _
from corehq.apps.userreports.reports.specs import PieChartSpec, \
    MultibarAggregateChartSpec, MultibarChartSpec, \
    FieldColumn, PercentageColumn, ExpandedColumn, AggregateDateColumn, \
    OrderBySpec, LocationColumn, ExpressionColumn


class ReportColumnFactory(object):
    class_map = {
        'aggregate_date': AggregateDateColumn,
        'expanded': ExpandedColumn,
        'field': FieldColumn,
        'percent': PercentageColumn,
        'location': LocationColumn,
        'expression': ExpressionColumn,
    }

    @classmethod
    def from_spec(cls, spec):
        column_type = spec.get('type') or 'field'
        if column_type not in cls.class_map:
            raise BadSpecError(
                'Unknown or missing column type: {} must be in [{}]'.format(
                    column_type,
                    ', '.join(cls.class_map)
                )
            )
        try:
            return cls.class_map[column_type].wrap(spec)
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
            raise BadSpecError(_('Illegal chart type: {0}, must be one of the following choice: ({1})').format(
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
