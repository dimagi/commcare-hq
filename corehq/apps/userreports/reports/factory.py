import json
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from django.utils.translation import ugettext as _
from corehq.apps.userreports.reports.filters.specs import ReportFilter
from corehq.apps.userreports.reports.specs import PieChartSpec, \
    MultibarAggregateChartSpec, MultibarChartSpec, \
    FieldColumn, PercentageColumn, ExpandedColumn, AggregateDateColumn, \
    OrderBySpec


class ReportFactory(object):

    @classmethod
    def from_spec(cls, spec):
        from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
        order_by = [(o['field'], o['order']) for o in spec.sort_expression]
        return ConfigurableReportDataSource(
            domain=spec.domain,
            config_or_config_id=spec.config_id,
            filters=[ReportFilter.wrap(f) for f in spec.filters],
            aggregation_columns=spec.aggregation_columns,
            columns=spec.report_columns,
            order_by=order_by,
        )


class ReportColumnFactory(object):
    class_map = {
        'aggregate_date': AggregateDateColumn,
        'expanded': ExpandedColumn,
        'field': FieldColumn,
        'percent': PercentageColumn,
    }

    @classmethod
    def from_spec(cls, spec):
        column_type = spec.get('type') or 'field'
        if column_type not in cls.class_map:
            raise BadSpecError(
                'Unknown or missing column type: {} must be in [{}]'.format(
                    column_type,
                    ', '.join(cls.class_map.keys())
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
                ', '.join(cls.spec_map.keys())
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
