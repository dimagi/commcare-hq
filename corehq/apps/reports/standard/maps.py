import re

from django.conf import settings

from dimagi.utils.modules import to_function

from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.standard import (
    ProjectReport,
    ProjectReportParametersMixin,
)


class GenericMapReport(ProjectReport, ProjectReportParametersMixin):
    """instances must set:
    data_source -- config about backend data source
    display_config -- configure the front-end display of data

    consult docs/maps.html for instructions
    """

    report_partial_path = "reports/partials/maps.html"
    flush_layout = True

    # override on subclass. It must be a dict with keys:
    # * report: fully qualified path to a ReportDataSource class
    # * report_params (optional): params to pass to the data source. This get's
    #     augmented with the `domain` and `request` params.
    data_source = None

    def _get_data(self):
        data = self._get_data_report(self.data_source, dict(self.request.GET.items()))
        return self._to_geojson(data, "geo")

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

        assert issubclass(DataSource, ReportDataSource), \
            f"[{params['report']}] does not implement the ReportDataSource API!"

        return DataSource(config).get_data()

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
