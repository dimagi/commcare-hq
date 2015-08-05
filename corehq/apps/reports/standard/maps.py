import json
import os.path
import re
from django.conf import settings
from django.utils.translation import ugettext_noop
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericReportView, GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.standard.cases.basic import CaseListMixin, CaseListReport
from dimagi.utils.modules import to_function
from django.template.loader import render_to_string


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
        data = loader(self.data_source, dict(self.request.GET.iteritems()))

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

                properties = dict((k, v) for k, v in row.iteritems() if k != geo_col)
                # handle 'display value / raw value' fields (for backwards compatibility with
                # existing data sources)
                # note: this is not ideal for the maps report, as we have no idea how to properly
                # format legends; it's better to use a formatter function in the maps report config
                display_props = {}
                for k, v in properties.iteritems():
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
                    root = list(root) + [unicode(e.html)]
                for sub in e:
                    for k in _headers(sub, root):
                        yield k
            else:
                yield root + [unicode(e.html)]
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
            case = CommCareCase.wrap(data['_case']).get_json()
            del data['_case']

            data['num_forms'] = len(case['xform_ids'])
            standard_props = (
                'case_name',
                'case_type',
                'date_opened',
                'external_id',
                'owner_id',
             )
            data.update(('prop_%s' % k, v) for k, v in case['properties'].iteritems() if k not in standard_props)

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
    report_partial_path = "reports/async/partials/maps.html"
    ajax_pagination = True
    asynchronous = True
    flush_layout = True

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


class DemoMapReport(GenericMapReport):
    """this report is a demonstration of the maps report's capabilities
    it uses a static dataset
    """

    name = ugettext_noop("Maps: Highest Mountains")
    slug = "maps_demo"
    data_source = {
        "adapter": "csv",
        "geo_column": "geo",
        "path": os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tests/maps_demo/mountains.csv'),
    }
    display_config = {
        "name_column": "name",
        "detail_columns": [
            "rank",
            "height",
            "prominence",
            "country",
            "range",
            "first_ascent",
            "num_ascents",
            "num_deaths",
            "death_rate"
        ],
        "column_titles": {
            "name": "Mountain",
            "country": "Country",
            "height": "Elevation",
            "prominence": "Topographic Prominence",
            "range": "Range",
            "first_ascent": "First Ascent",
            "rank": "Ranking",
            "num_ascents": "# Ascents",
            "num_deaths": "# Deaths",
            "death_rate": "Death Rate"
        },
        "enum_captions": {
            "first_ascent": {
                "_null": "Unclimbed"
            },
            "rank": {
                "-": "Top 10"
            }
        },
        "numeric_format": {
            "rank": "return '#' + x",
            "height": "return x + ' m | ' + Math.round(x / .3048) + ' ft'",
            "prominence": "return x + ' m | ' + Math.round(x / .3048) + ' ft'",
            "death_rate": "return (100. * x).toFixed(2) + '%'"
        },
        "metrics": [
            {
                "color": {
                    "column": "rank",
                    "thresholds": [
                        11,
                        25,
                        50
                    ]
                }
            },
            {
                "color": {
                    "column": "height",
                    "colorstops": [
                        [
                            7200,
                            "rgba(20,20,20,.8)"
                        ],
                        [
                            8848,
                            "rgba(255,120,20,.8)"
                        ]
                    ]
                }
            },
            {
                "size": {
                    "column": "prominence"
                },
                "color": {
                    "column": "prominence",
                    "thresholds": [
                        1500,
                        3000,
                        4000
                    ],
                    "categories": {
                        "1500": "rgba(255, 255, 60, .8)",
                        "3000": "rgba(255, 128, 0, .8)",
                        "4000": "rgba(255, 0, 0, .8)",
                        "-": "rgba(150, 150, 150, .8)"
                    }
                }
            },
            {
                "icon": {
                    "column": "country",
                    "categories": {
                        "Pakistan": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAIAAACAzcMBAAAABmJLR0QA/wD/AP+gvaeTAAAAw0lEQVQ4y2P4jwr2nz/G6ChDKmIYUqZIBhvGtRewuyoiCcqSZopylNXhyyc53JTgIlHN2UZpHqSZsuPUgcpZ7XCuXV7Qm4/vyma0kGCKVIjRv3//oltykDWE1KdJhxiTYIpphhdQpHpOJ0WhC3HL7Sf3Od2V0bQxO8mRFi5AwfWHd/B7a8AFgYZ6lMWQFkdP37wAir98/7pz+bSKWW1dK6av2L8ROdaITS+T1s178vr5n79/rty/WTq9GTXtDL0cQAwCAFS5mrmuqFgRAAAAAElFTkSuQmCC",
                        "China/Pakistan": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB90IHwcYMYz0J78AAAFiSURBVDjLY3g/tfM/Oj5Xm/M/z1Tsf565GIQmEzMgG/phbgeK4eVpQv/zralk+PfDrf8/LW2HG54PdHm+jdj/Ii8R8g3/MLvj/8/zLf//v2/8//914/+rCzPhCgqAhhf7QQyvslP8PzfS8X+huSSaQeL4Xf5pSfv/Pw+a/v++1YwIc5gFtmL/651U/1+oz/tfZIFq8Oxwu//tHjr4Df+4CBjeMyD0+QaE4YWuov9LI4X/n67K/L86yQdFc6+P4f+nfQ3/VyZ6Ew5z9NRSFg+J0Gp7xf/vpnb8nxNuj2HAjFAboLwS6YYXOIqC6U5PXbD4mmRf8lMLRjqHYpjL73RUAsNcCqtB+Wbi5BkOwqAwB8kdK0/9X2olgyIHsnBSgBn5hoNSy6OeWrD8k976/5szQ/6vAkbwFiB9uDQRIxWRZDgsne/Iifj/sLv2/9sp7f9vtpYBU4oXlnRPhuEUZf8hZTgA8YnkUuk5wigAAAAASUVORK5CYII=",
                        "Bhutan/China": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAABmJLR0QA/wD/AP+gvaeTAAAB5UlEQVQ4y63Q20uTARzGcf+ctTWsiAbFmstRGXXRwYIgKqGRwaib6krwKhdkB6I1h+AsOhlkrHVYh2lTslndaLVDc+/51Ls5urK7bxeBIFrtDS+eu9/z4eHX0kh5We3U73vRu9bQsmpgqpVGysv3Pg/Kdhey3+Uc10d9VF+F0XJnsZ8FfsNP1mM/3ot21I3sdy3GEW6n/Rj5PrTPaUy1yo9GDaE0jZW7hRyL8m335v/H65kQczNv0OQKplKkZhmIDxOIQzeQ9geXwI5x62k7+tcMlmUhvBhk7kCQQvwacjKGeOY4YsDjHLdyEex8D+Z4GG20C70wi5B/h/llFvHta+ofp1CvX3S+XMtHma+ZGMIMUqWI9X4CtVxGmZpEOt+N2OFbtrgp3EpvxSxlKb28jHKqA6X3HFKsH+HDNFK0B9nvQmxvXRH+J25nwwjlAuLIbbQ7g0g7NyHu2UIpfgX90V2se0OoyTjVZvFaaiNm9hjaRILyWIbi8ADV4QGkxFWUg6ElZT15k58LC0i7fE3g6Q3Y4xFqpU8IqRHUyBGkE50Iz9Mo4UPLykpoHcK+tubeYsS3YVw4jRT0Lh5Uwp2Yk2NUug//EfkrPv/Ai3HSveKB1ObBvNSLHHA7x+3+tag7XI6LzeQXCpSkKvvyoHIAAAAASUVORK5CYII=",
                        "China/India": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB90IHwcUGGLz8N8AAADoSURBVDjLY3ifpPQfJ07GI0cEZkDmfMhURJH8MVn2/4d0ReoY/n2C3P9PhQooLv+Qofj/c5kC+YaDXPdztuz//7ul/v/fIfX/a5s8im8+VytQ5vJPBQr//6yR/v97uQyGIvTgIt7wqZ3/Qfjjoo7/72dA6Zkd/2Hin5a2//+6s+3/leqa/3uSisA0TI4QZsAn+X1/6/8Pszv+X6qo/n+mqPL/qYKK/6eB9KXKasoN/7gQ4oOdCYVgg5d4Z4LpnfGFlBsOwyCXnoa5vLCCOi5HxqCw3g0M86vVtcSHeXkk939a4VHD6W84AMcMSEsYuXzSAAAAAElFTkSuQmCC",
                        "India/Nepal": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB90IHwcVISTtSZYAAAHKSURBVDjLrZDRS5NRGId3111Q/4H3GULpkopUUihoKgjbhcoCY9GNIZP2OflK55wOdblE3EWtGmWCxpTpZwgqJTnTIFQUJQmT2EVOcSip0J7mAWOsVX6yFx5e3pfD8zvnaPCcI55eSzGRDi2J++OgSVwEjDpGjdeYri8g2pViuWK8QViv5avhIq9NRay1XU69/JCPpVcZla6z33k+9fIDQoZs+isKWXLmqpQnlPIowMZDH5GeYX5Mz7PlGxDz3F03z0rduNvHiOzscZRKKt8eec/+ypqYdxdWWOgc4IOpjeCtVoImF4+lbqZmvxGNRtXLN1zP2Vv6ws+tbXY/LTKsdwixL0cWXSlp5HPrC/p8E4TWd9TJw84ngnWnF3/HEM0NQzjuD2KXA7EewNWk4H81ib8nyEtlkeXVTfXycIuX77GAXu844+9W8XhmmZkJcdTSnG46QTxX9FlU69KolfKRHUVY7+Vhjs1nyrI5ZTtJ4vl/kVRuNefQ4K/C8bYOW/cdpNtZIiBdZcCfcoMW2a4T4gMax2RqrQXiNeZCdQFJb15TeYm6pxXY30g88JQjmTKFXG3AX//ccjMDa3UuFmPGb3F8wNmyC/8N+AVYXqHDIJue6wAAAABJRU5ErkJggg==",
                        "Nepal": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAARCAYAAADtyJ2fAAAABmJLR0QA/wD/AP+gvaeTAAABnElEQVQoz2NgMe9fzWA9WYqBVJCpnvW/WjXpt4RpVwkDQwMT0Rrz1DL+3xGx+X9M3OWft3bJcwbzSRYkaYThmXLhf3SMGucx6HVzk6QRhC+IOf6L1Cz4yGA5xQevxnsKbv+fBhX8/zB95f/HrilgPsiAlTKBf0wM6w9iDTyQxldlPf+/7j7+HwQ+rdv9/0VaA9z2GyJ2/wvV0n7ymvUWoQQe2EY5l/9fNh/4//vJy/8fF2z4f1fCHsP5O6W8/rvoVDxgsJpqgOHHWyK2/xM1cv5b6tU8dNSrvIKO7fWqLrOZT9zJYD7FCzVwxO2ATrP976lT9prBcro0UaH6Mrv1/9v2OWD/3QRq9tEpfYtXM0jji4Tq/79uPQQHzvcTF/8/8cwAa/bXxqM5Xz3z/9vmGf9h4N+Pn/9f5rVD/CwK0lyCXTPIxmdhxf+/7Dr6/8+b9/8/rd75/4l7GiLAcGmG+fGRVfT/F0m1/x9aRmNEBUhzgHYxqmZsSQ4bvgnUHKhV9JrBfII4WKOxQf3/dGDWIgbHa+b9ZzObcAOkGQDaD1JZd6jOSgAAAABJRU5ErkJggg==",
                        "India": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAABmJLR0QA/wD/AP+gvaeTAAAAdElEQVQ4y2P4P9P4P60ww6jhA2A4keD06Wf/Z826BKaJBUQZfuzY4/+7dt3/v23b3f87d97/f/z4E+oZPnXqebDBOTn7wfSUKeepZzjIpSAXb9t27/+OHfeo63JYmM+ceen/mTPPiQ9zoQ72/7TCo4bT33AAzkG28NnasBMAAAAASUVORK5CYII=",
                        "China/Nepal": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB90IHwcYDjqSCoIAAAG4SURBVDjLY7inKfAfGU/Ts/p/WUscwtdBlSMVMyBzHlrw/1+iYfN/nbrF/0062v/fd7P/f2DCTx3D37dx/F9lbvX/rrza/0sKWv/n6tj+P24m+/9ZMA/5hoNc93ke2///9xj+b28w+f/ERRlsAQjv0zb6v87f4P8tTSHyXf7Enff/zwPM/zfnmcINhuGb6hr/F2ja/t+rrUKe4Y+d+f7f1xP4v9LE6v99Da3/D23t/z+PjwFaavH/qacG2JIjygb/5+tYIiKclDAH4eUa1v+f+Pv+f1mY9f/bvqb/LwtS/j92d4f74ra8+v+VGpb/NwAj/C45ht9T0fr/Mjf9/7uJVf+fp8T/v6eojhFUZ5R0/8/Wsv1/UluWNMNhBtwBYlBYT9O2/z9X2xornqhnB4x0ZdINv6ugDgwGtf+ztOyIDmeiDH/s5fX/aXgoOLxBPphNhgVYDX/s4vr/TUP5/3eT2/6/qsj//9DSGmzBHBItwGK4zf+nocFgg8G4v/n/Y29veByQYgFWlz+ydwQmxcz/bzvr/r/ITAGWOVYokUysBTjD/IGh6f/Hrm7/7xti5liQBXOByZCQBQC9TOVO1zHzuwAAAABJRU5ErkJggg==",
                        "China/Kyrgyzstan": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAOCAYAAADE84fzAAAABmJLR0QA/wD/AP+gvaeTAAABFUlEQVQ4y82UsUoDQRCGv9m9XG4PQgjaiCSlwUJtrC31lXxJtRAjKChBi1glXtSce7c7FnkAj5wB/2aa4YP5Z/6R2eBI2ZIMW1RzuABW17WhkkZN4xK77zE7AYDqLqOeuPbwzvGK9GxJ52SFrgScYkbfGKf4q3xzuPQi6eknyUFJfZ9BHuDLkgw9elhSPXXRud3Mc7NbYUeeOE8w/YCfOMgjcWGx4xJJY4uFVoJ6IX5YwsLSv5xBKWiRIEEwvRbwuLSEaRe75wnPKdWto3rMMENPeO0Q3pLNPdd3i79xyCDQPS/QwpJdFNQPGf46R5e23bXUEwdRCC8pgqJBCNP1FL9Go3H8DWAUFAjydyFaLwCI8n9+yw+uh21xPR0lJAAAAABJRU5ErkJggg==",
                        "China": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAIAAACAzcMBAAAABmJLR0QA/wD/AP+gvaeTAAAAjUlEQVQ4y2O4pymABekIYBfHgRjgrIcW/HD2hx72Byb85Jjyvo3jiQcvhH1fR+CBGf+zYB4STAFa+3ke2/97DP+uM74u4oI6zZz/eQwPaW554s778wDz960syHLIfiTKlMfOfPf1BB458d03gOp84skLdxcJ4YKM3tVxkBm6yOiRAx+ZMU0JGjVl8JsCABF+frZhYhUiAAAAAElFTkSuQmCC",
                        "China/India/Nepal": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAAAXNSR0IArs4c6QAAAAZiS0dEAP8A/wD/oL2nkwAAAAlwSFlzAAALEwAACxMBAJqcGAAAAAd0SU1FB90IHwcVCRFY4WwAAAH0SURBVDjLrZJPTxNRFMV/bzptp50ptilCaQsIQSVGcaFLEz+HWzd+BL+eKxdiXFDEuJEAIqX/S9vpMDPvXRdKLAH/DPHs3rvJOfeec1T/5bowg21/iUe5No6KQQGXpslgzT5UVnB84aBbYv+8iPM4QqXl/5Bn72tSecNaOKbci3j7ZoWedrDnzY3IbQCVFnJPYzJ3NLlpjP3Z4DThoT+gZfJ0HJc1GWArk3xziRTnH1PooUKPLeLmr4MWgoDaQcBuf5Fm7CXc/MkrAKQgjDqKUI9hc0Jq7hapShnTP8FmQqXhs99V7C4v8OyBh5NK4LkZKdBgAoVdq5DeWMZ9XsWur9DpFghDQzWj2Wg12X7f5suZQiRBoBeID5ugDeFRhASazt4RInBy4qNEKDfbFI9bfDiMGIbqz4FeZdcE7xoI8Clb5LhWQ8UGKQg9IF22CD0XC9jrK9bnYDEn/0h+0XtLsXk+QJfmKaVDeqcTqksu1epssL9vkHr9wr0kqfur3A3PsJcrWHkHM/aJjlvs5IrkCl+xVZSs51c+l26TubeK5eXR3SEyDdjqDdihnkjgmkAVlpfH8vIApEoFlOeigK3pgOmoTizpm5ILejgiPu0iYUT0rY2MJj9lkwlca4tu9ZBpgFVwMWcTzNifueuHQIM6zl8s+g5AOt+1kjl9KgAAAABJRU5ErkJggg==",
                        "Afghanistan/Pakistan": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPCAYAAAAPr1RWAAAABmJLR0QA/wD/AP+gvaeTAAAA50lEQVQ4y2NgYGD4jws7A/F+PNg5GahuJh48ajjZhh9gZf1/Sk/v/xlz8/+n9PX/H5WSoo7hR2Ul/p/2sPl/WFzo/+XgwP+HJUX+n3ex/n9YXpJyw8952/4/Zarz/2KA+/+Hc3r/X/Rz+3/SXPf/OU9ryg2/mhL0/0p67P9Lcf7/zwc4/T8f7g7mX00Jptzwi+Fe/8+62fy/lh3//97kxv+XYoP/n3W3/X8+wodyw4/pqv+/Upj4/6wH0NXu7v/PejoD+Qn/j+qqUSe1HFGV+f9iycL/T+fN+v9ixdL/R5SlRzPRIDUcAOepDzYPRuOVAAAAAElFTkSuQmCC",
                        "Tajikistan": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAMCAYAAACJOyb4AAAABmJLR0QA/wD/AP+gvaeTAAAAkElEQVQ4y2M4w8Dwn1aYYega/nrmzP/E4jezp/wnRT3Df6LAv///vlz4/+/7bTAN4hMDiDIcYuD//39fzEXhU274v9///329DKR//f/zdjOYhvB/U8nl3278/wN09e+Xi/7/eTkHzCfK5TMPzfxPCM8+NPX/+sMl/5ccavu/4VAJmE+MPgaGNGCSoRUesoYDAFwH0YKibe8HAAAAAElFTkSuQmCC"
                    }
                }
            },
            {
                "color": {
                    "column": "range"
                }
            },
            {
                "color": {
                    "column": "first_ascent",
                    "thresholds": [
                        1940,
                        1955,
                        1970,
                        1985,
                        2000
                    ],
                    "categories": {
                        "1940": "rgba(38, 75, 89, .8)",
                        "1955": "rgba(36, 114, 117, .8)",
                        "1970": "rgba(50, 153, 132, .8)",
                        "1985": "rgba(95, 193, 136, .8)",
                        "2000": "rgba(159, 230, 130, .8)",
                        "-": "rgba(33, 41, 54, .8)",
                        "_null": "rgba(255, 255, 0, .8)"
                    }
                }
            },
            {
                "size": {
                    "column": "num_ascents",
                    "baseline": 100
                }
            },
            {
                "size": {
                    "column": "num_deaths",
                    "baseline": 100
                }
            },
            {
                "color": {
                    "column": "death_rate",
                    "colorstops": [
                        [
                            0,
                            "rgba(20,20,20,.8)"
                        ],
                        [
                            0.4,
                            "rgba(255,0,0,.8)"
                        ]
                    ]
                }
            },
            {
                "title": "Ascents vs. Death Rate",
                "size": {
                    "column": "num_ascents",
                    "baseline": 200
                },
                "color": {
                    "column": "death_rate",
                    "colorstops": [
                        [
                            0,
                            "rgba(20,20,20,.8)"
                        ],
                        [
                            0.4,
                            "rgba(255,0,0,.8)"
                        ]
                    ]
                }
            }
        ]
    }

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return user and user.is_previewer()

class DemoMapReport2(GenericMapReport):
    """this report is a demonstration of the maps report's capabilities
    it uses a static dataset
    """

    name = ugettext_noop("Maps: States of India")
    slug = "maps_demo2"
    data_source = {
        "adapter": "geojson",
        "geo_column": "geo",
        "path": os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tests/maps_demo/india.geojson'),
    }
    display_config = {
        'name_column': 'name',
        'detail_columns': ['iso', 'type', 'pop', 'area', 'pop_dens', 'lang', 'literacy', 'urbanity', 'sex_ratio'],
        'column_titles': {
            'name': 'State/Territory',
            'iso': 'ISO 3166-2',
            'type': 'Type',
            'pop': 'Population',
            'area': 'Area',
            'pop_dens': 'Population Density',
            'lang': 'Primary Official Language',
            'literacy': 'Literacy Rate',
            'urbanity': '% Urban',
            'sex_ratio': 'Sex Ratio',
        },
        'numeric_format': {
            'iso': "return 'IN-' + x",
            'area': "return x + ' km^2'",
            'pop': "return x.toString().replace(/\B(?=(?:\d{3})+(?!\d))/g, ',')",
            'pop_dens': "return x + ' /km^2'",
            'literacy': "return x + '%'",
            'urbanity': "return x + '%'",
            'sex_ratio': "return x/1000. + ' females per male'",
        },
        'metrics': [
            {'color': {'column': 'pop'}},
            {'color': {'column': 'pop_dens',
                       'colorstops': [
                        [0, 'rgba(20, 20, 20, .8)'],
                        [1200, 'rgba(255, 120, 0, .8)'],
                        ]}},
            {'color': {'column': 'area'}},
            {'color': {'column': 'lang',
                       'categories': {
                        'Bengali': 'hsla(0, 100%, 50%, .8)',
                        'English': 'hsla(36, 100%, 50%, .8)',
                        'Gujarati': 'hsla(72, 100%, 50%, .8)',
                        'Hindi': 'hsla(108, 100%, 50%, .8)',
                        'Kannada': 'hsla(144, 100%, 50%, .8)',
                        'Nepali': 'hsla(180, 100%, 50%, .8)',
                        'Punjabi': 'hsla(216, 100%, 50%, .8)',
                        'Tamil': 'hsla(252, 100%, 50%, .8)',
                        'Telugu': 'hsla(288, 100%, 50%, .8)',
                        'Urdu': 'hsla(324, 100%, 50%, .8)',
                        '_other': 'hsla(0, 0%, 60%, .8)',
                        }
                       }},
            {'color': {'column': 'literacy',
                       'colorstops': [
                        [60, 'rgba(20, 20, 20, .8)'],
                        [100, 'rgba(255, 120, 0, .8)'],
                        ]}},
            {'color': {'column': 'urbanity',
                       'colorstops': [
                        [10, 'rgba(20, 20, 20, .8)'],
                        [50, 'rgba(255, 120, 0, .8)'],
                        ]}},
            {'color': {'column': 'sex_ratio',
                       'colorstops': [
                        [850, 'rgba(20, 20, 255, .8)'],
                        [1050, 'rgba(255, 20, 20, .8)'],
                        ]}},
        ],
    }

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return user and user.is_previewer()

class GenericCaseListMap(GenericMapReport):
    fields = CaseListMixin.fields

    # override to specify geo-properties of case types
    # (beyond default 'gps' case property)
    case_config = {}

    @property
    def data_source(self):
        return {
            "adapter": "case",
            "geo_fetch": self.case_config,
        }

    @property
    def display_config(self):
        cfg = {
            "name_column": "case_name",
            "detail_columns": [
                'external_id',
                'owner_name',
                'num_forms',
                'is_closed',
                'opened_on',
                'modified_on',
                'closed_on',
            ],
            "column_titles": {
                'case_name': 'Case Name',
                'case_type': 'Case Type',
                'external_id': 'ID #',
                'owner_name': 'Owner',
                'num_forms': '# Forms',
                'is_closed': 'Status',
                'opened_on': 'Date Opened',
                'modified_on': 'Date Last Modified',
                'closed_on': 'Date Closed',
            },
            "enum_captions": {
                "is_closed": {'y': 'Closed', 'n': 'Open'},
            },
        }
        cfg['detail_template'] = render_to_string('reports/partials/caselist_mapdetail.html', {})
        return cfg

    def dynamic_config(self, static_config, data):
        all_cols = reduce(lambda a, b: a.union(b), (row['properties'] for row in data), set())
        all_props = filter(lambda e: e.startswith('prop_'), all_cols)

        # TODO feels like there should be a more authoritative source of property titles
        def format_propname(prop):
            name = prop[len('prop_'):]
            name = reduce(lambda str, sep: ' '.join(str.split(sep)), ('-', '_'), name).title()
            return name

        static_config['column_titles'].update((prop, format_propname(prop)) for prop in all_props)
        static_config['detail_columns'].extend(sorted(all_props))

        metric_cols = [k for k in static_config['detail_columns'] if k not in ('external_id')]
        metric_cols.insert(0, 'case_type')
        static_config['metrics'] = [{'auto': col} for col in metric_cols]

        return static_config

class DemoMapCaseList(GenericCaseListMap):
    name = ugettext_noop("Maps: Case List")
    slug = "maps_demo_caselist"

    case_config = {
        "supply-point": "_random",
        "supply-point-product": "_random",
    }

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return user and user.is_previewer()

"""
metrics:
want to allow customization
"""
