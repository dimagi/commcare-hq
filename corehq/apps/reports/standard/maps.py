import json
import re

from django.conf import settings

import csv

from casexml.apps.case.models import CommCareCase
from dimagi.utils.modules import to_function

from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.generic import GenericReportView, GenericTabularReport
from corehq.apps.reports.standard import (
    ProjectReport,
    ProjectReportParametersMixin,
)
from corehq.apps.reports.standard.cases.basic import CaseListReport


class GenericMapReport(ProjectReport, ProjectReportParametersMixin):
    """instances must set:
    data_source -- config about backend data source
    display_config -- configure the front-end display of data

    consult docs/maps.html for instructions
    """

    report_partial_path = "reports/partials/maps.html"
    flush_layout = True
    #asynchronous = False

    def _get_data(self):
        adapter = self.data_source['adapter']
        geo_col = self.data_source.get('geo_column', 'geo')

        try:
            loader = getattr(self, '_get_data_%s' % adapter)
        except AttributeError:
            raise RuntimeError('unknown adapter [%s]' % adapter)
        data = loader(self.data_source, dict(self.request.GET.items()))

        return self._to_geojson(data, geo_col)

    def _to_geojson(self, data, geo_col):
        def _parse_geopoint(raw):
            try:
                latlon = [float(k) for k in re.split(' *,? *', raw)[:2]]
                return [latlon[1], latlon[0]] # geojson is lon, lat
            except ValueError:
                return None

        metadata = {}

        def points():
            for row in data:
                if '_meta' in row:
                    # not a real data row
                    metadata.update(row['_meta'])
                    continue

                geo = row[geo_col]
                if geo is None:
                    continue

                e = geo
                depth = 0
                while hasattr(e, '__iter__'):
                    e = e[0]
                    depth += 1

                if depth < 2:
                    if depth == 0:
                        geo = _parse_geopoint(geo)
                        if geo is None:
                            continue
                    feature_type = 'Point'
                else:
                    if depth == 2:
                        geo = [geo]
                        depth += 1
                    feature_type = 'MultiPolygon' if depth == 4 else 'Polygon'

                properties = dict((k, v) for k, v in row.items() if k != geo_col)
                # handle 'display value / raw value' fields (for backwards compatibility with
                # existing data sources)
                # note: this is not ideal for the maps report, as we have no idea how to properly
                # format legends; it's better to use a formatter function in the maps report config
                display_props = {}
                for k, v in properties.items():
                    if isinstance(v, dict) and set(v.keys()) == set(('html', 'sort_key')):
                        properties[k] = v['sort_key']
                        display_props['__disp_%s' % k] = v['html']
                properties.update(display_props)

                yield {
                    'type': 'Feature',
                    'geometry': {
                        'type': feature_type,
                        'coordinates': geo,
                    },
                    'properties': properties,
                }

        features = list(points())
        return {
            'type': 'FeatureCollection',
            'features': features,
            'metadata': metadata,
        }

    def _get_data_report(self, params, filters):
        # this ordering is important!
        # in the reverse order you could view a different domain's data just by setting the url param!
        config = dict(filters)
        config.update(params.get('report_params', {}))
        config['domain'] = self.domain
        config['request'] = self.request

        DataSource = to_function(params['report'])

        assert issubclass(DataSource, ReportDataSource), '[%s] does not implement the ReportDataSource API!' % params['report']
        assert not issubclass(DataSource, GenericReportView), '[%s] cannot be a ReportView (even if it is also a ReportDataSource)! You must separate your code into a class of each type, or use the "legacyreport" adapater.' % params['report']

        return DataSource(config).get_data()

    def _get_data_legacyreport(self, params, filters):
        Report = to_function(params['report'])
        assert issubclass(Report, GenericTabularReport), '[%s] must be a GenericTabularReport!' % params['report']

        # TODO it would be nice to indicate to the report that it was being used in a map context, (so
        # that it could add a geo column) but it does not seem like reports can be arbitrarily
        # parameterized in this way
        report = Report(request=self.request, domain=self.domain, **params.get('report_params', {}))

        def _headers(e, root=[]):
            if hasattr(e, '__iter__'):
                if hasattr(e, 'html'):
                    root = list(root) + [str(e.html)]
                for sub in e:
                    for k in _headers(sub, root):
                        yield k
            else:
                yield root + [str(e.html)]
        headers = ['::'.join(k) for k in _headers(report.headers)]

        for row in report.rows:
            yield dict(zip(headers, row))

    @property
    def report_context(self):
        layers = getattr(settings, 'MAPS_LAYERS', None)
        if not layers:
            layers = {'Default': {'family': 'fallback'}}

        data = self._get_data()
        display = self.dynamic_config(self.display_config, data['features'])

        context = {
            'data': data,
            'config': display,
            'layers': layers,
        }

        return dict(
            context=context,
        )

    def dynamic_config(self, static_config, data):
        """override to customize the display configuration based on the
        resultant data

        static_config -- contents of 'display_config' property
        data -- report data as a list of geojson Feature records
        """
        return static_config

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True
