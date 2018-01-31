from collections import OrderedDict

ROOT_LOCATION_TYPE = "TOP"

LOCATION_SHEET_HEADERS = OrderedDict([
    ('location_id', 'location_id'),
    ('site_code', 'site_code'),
    ('name', 'name'),
    ('parent_code', 'parent_site_code'),
    ('external_id', 'external_id'),
    ('latitude', 'latitude'),
    ('longitude', 'longitude'),
    ('do_delete', 'Delete(Y/N)'),
    ('custom_data', 'data'),
    ('uncategorized_data', 'uncategorized_data'),
    ('delete_uncategorized_data', 'Delete Uncategorized Data(Y/N)'),
])

LOCATION_TYPE_SHEET_HEADERS = OrderedDict([
    ('code', 'code'),
    ('name', 'name'),
    ('parent_code', 'parent_code'),
    ('do_delete', 'Delete(Y/N)'),
    ('shares_cases', 'Shares Cases Y/N'),
    ('view_descendants', 'View Child Cases (Y/N)'),
])

LOCK_LOCATIONS_TIMEOUT = 60 * 60 * 10  # seconds
