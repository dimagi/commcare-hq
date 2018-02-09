from __future__ import absolute_import
import json
import os.path
import re
from django.conf import settings
from django.utils.translation import ugettext_noop
from casexml.apps.case.models import CommCareCase
from corehq import toggles
from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.generic import GenericReportView, GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.standard.cases.basic import CaseListMixin, CaseListReport
from corehq.apps.hqwebapp.decorators import use_maps_async
from dimagi.utils.modules import to_function
from django.template.loader import render_to_string
import six
from six.moves import zip


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
        data = loader(self.data_source, dict(six.iteritems(self.request.GET)))

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

                properties = dict((k, v) for k, v in six.iteritems(row) if k != geo_col)
                # handle 'display value / raw value' fields (for backwards compatibility with
                # existing data sources)
                # note: this is not ideal for the maps report, as we have no idea how to properly
                # format legends; it's better to use a formatter function in the maps report config
                display_props = {}
                for k, v in six.iteritems(properties):
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
                    root = list(root) + [six.text_type(e.html)]
                for sub in e:
                    for k in _headers(sub, root):
                        yield k
            else:
                yield root + [six.text_type(e.html)]
        headers = ['::'.join(k) for k in _headers(report.headers)]

        for row in report.rows:
            yield dict(zip(headers, row))

    def _get_data_case(self, params, filters):
        MAX_RESULTS = 200 # TODO vary by domain (cc-plus gets a higher limit?)
        # bleh
        _get = self.request.GET.copy()
        _get['iDisplayStart'] = '0'
        _get['iDisplayLength'] = str(MAX_RESULTS)
        self.request.GET = _get

        source = CaseListReport(self.request, domain=self.domain)

        total_count = source.es_results['hits']['total']
        if total_count > MAX_RESULTS:
            # can't really think of a better way to return out-of-band
            # metadata from a generator
            yield {'_meta': {
                    'total_rows': total_count,
                    'capped_rows': MAX_RESULTS,
                }}

        # TODO ideally we'd want access to all the data shown on the
        # case detail report. certain case types can override this via
        # case.to_full_dict(). however, there is currently no efficient
        # way to call this over a large block of cases. so now we (via the
        # CaseListReport/DataSource) limit ourselves only to that which
        # can be queried in bulk

        for data in source.get_data():
            case = CommCareCase.wrap(data['_case']).to_api_json()
            del data['_case']

            data['num_forms'] = len(case['xform_ids'])
            standard_props = (
                'case_name',
                'case_type',
                'date_opened',
                'external_id',
                'owner_id',
             )
            data.update(('prop_%s' % k, v) for k, v in six.iteritems(case['properties']) if k not in standard_props)

            GEO_DEFAULT = 'gps' # case property
            geo = None
            geo_directive = params['geo_fetch'].get(data['case_type'], GEO_DEFAULT)
            if geo_directive.startswith('link:'):
                # TODO use linked case
                pass
            elif geo_directive == '_random':
                # for testing -- just map the case to a random point
                import random
                import math
                geo = '%s %s' % (math.degrees(math.asin(random.uniform(-1, 1))), random.uniform(-180, 180))
            elif geo_directive:
                # case property
                geo = data.get('prop_%s' % geo_directive)

            if geo:
                data['geo'] = geo
                yield data

    def _get_data_csv(self, params, filters):
        import csv
        with open(params['path']) as f:
            return list(csv.DictReader(f))

    def _get_data_geojson(self, params, filters):
        with open(params['path']) as f:
            data = json.load(f)

        for feature in data['features']:
            item = dict(feature['properties'])
            item['geo'] = feature['geometry']['coordinates']
            yield item

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


class ElasticSearchMapReport(GetParamsMixin, GenericTabularReport, GenericMapReport):

    report_template_path = "reports/async/maps.html"
    report_partial_path = "reports/partials/base_maps.html"
    ajax_pagination = True
    asynchronous = True
    flush_layout = True

    @use_maps_async
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(ElasticSearchMapReport, self).decorator_dispatcher(request, *args, **kwargs)

    def get_report(self):
        Report = to_function(self.data_source['report'])
        assert issubclass(Report, GenericTabularReport), '[%s] must be a GenericTabularReport!' % self.data_source['report']

        report = Report(request=self.request, domain=self.domain, **self.data_source.get('report_params', {}))
        return report

    @property
    def total_records(self):
        report = self.get_report()
        return report.total_records

    @property
    def json_dict(self):
        ret = super(ElasticSearchMapReport, self).json_dict
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
        ret.update(dict(context=context))
        return ret
