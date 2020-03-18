import io

from django.db.models import Q
from django.utils.functional import cached_property

from couchexport.export import export_raw

from corehq.apps.locations.models import LocationType, SQLLocation


class RequestTemplateDownload(object):
    def __init__(self, domain, parent_location_id, leaf_location_type):
        self.domain = domain
        self.headers = []
        location_types = [t.code for t in LocationType.objects.by_domain(domain)]
        for location_type in location_types:
            self.headers.extend([f'old_{location_type}', f'new_{location_type}'])
        self.parent_location_id = parent_location_id
        self.parent_location = SQLLocation.active_objects.get(location_id=self.parent_location_id)
        self.leaf_location_type = leaf_location_type

    @cached_property
    def _locations(self):
        return (
            SQLLocation.active_objects.get_descendants(Q(domain=self.domain, id=self.parent_location.id)).
            filter(location_type__code=self.leaf_location_type)
        )

    def dump(self):
        headers = [[self.leaf_location_type, self.headers]]
        stream = io.BytesIO()
        rows = [(self.leaf_location_type, self._generate_rows())]
        export_raw(headers, rows, stream)
        return stream

    def _generate_rows(self):
        rows = []
        for location in self._locations:
            rows.append(self._generate_row(location))
        return rows

    def _generate_row(self, location):
        def generate_row(loc):
            loc_location_type = loc.location_type
            return {f'old_{loc_location_type}': loc.site_code,
                    f'new_{loc_location_type}': ''}
        current_location = location
        row = generate_row(current_location)
        while current_location.parent_id:
            parent = self._ancestors[current_location.parent_id]
            row.update(generate_row(parent))
            current_location = parent
        return [row.get(k, '') for k in self.headers]

    @cached_property
    def _ancestors(self):
        location_ids = [loc.id for loc in self._locations]
        return {
            loc.id: loc for loc in
            SQLLocation.active_objects.get_ancestors(Q(domain=self.domain, id__in=location_ids))
        }
