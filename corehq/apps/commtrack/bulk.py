import csv
from StringIO import StringIO
from datetime import datetime
from corehq.apps.commtrack.models import *
from corehq.apps.sms.mixin import VerifiedNumber, strip_plus
from corehq.apps.locations.models import Location
from corehq.apps.users.models import CouchUser
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.commtrack import sms
from dimagi.utils.logging import notify_exception
from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.commtrack.util import get_supply_point

def set_error(row, msg, override=False):
    """set an error message on a stock report to be imported"""
    if override or 'error' not in row:
        row['error'] = msg

def set_error_bulk(rows, msg, override=False):
    """set an error message on a set of stock reports
    override - if False, don't set on rows that already have an error message
    """
    for row in rows:
        set_error(row, msg, override)

def import_stock_reports(domain, f):
    """bulk import entry point"""
    reader = csv.DictReader(f)
    data = list(reader)

    try:
        data_cols = validate_headers(domain, set(reader.fieldnames))
    except Exception, e:
        raise RuntimeError(str(e))

    for row in data:
        validate_row(row, domain, data_cols)

    # abort if any location codes are invalid
    if any(not row.get('loc') for row in data):
        set_error_bulk(data, 'SKIPPED because some rows could not be assigned to a valid location')
    
    else:

        rows_by_loc = map_reduce(lambda row: [(row['loc']._id,)], data=data, include_docs=True)
        for loc, rows in rows_by_loc.iteritems():
            process_loc(domain, loc, rows, data_cols)

    return annotate_csv(data, reader.fieldnames)
    
def validate_headers(domain, headers):
    """validate the headers of the csv -- make sure required fields are present
    and stock actions/products are valid (and parse the action/product info out
    of the header text
    """
    META_COLS = ['site_code', 'outlet_code', 'date', 'reporter', 'phone']

    if 'reporter' not in headers and 'phone' not in headers:
        raise RuntimeError('"reporter" or "phone" column required')
    if 'outlet_code' not in headers and 'site_code' not in headers:
        raise RuntimeError('"outlet_code" column required')
    if 'date' not in headers:
        raise RuntimeError('"date" column required')

    actions = CommtrackConfig.for_domain(domain).keywords()
    products = dict((p.code, p) for p in Product.view('commtrack/product_by_code', startkey=[domain], endkey=[domain, {}], include_docs=True))

    data_cols = {}
    for h in headers:
        if h in META_COLS:
            continue

        try:
            data_cols[h] = validate_data_header(h, actions, products)
        except Exception, e:
            msg = 'couldn\'t parse header "%s"' % h
            if str(e):
                msg += ': ' + str(e)
            raise RuntimeError(msg)
    return data_cols

def validate_data_header(header, actions, products):
    """parse and validate the action/product info out of a data metric column header"""
    pcs = header.lower().split()
    if pcs[0].startswith('data'):
        pcs = pcs[1:]
        
    try:
        action_code, prod_code = pcs
    except Exception, e:
        raise RuntimeError()

    if action_code not in actions:
        raise RuntimeError('don\'t recognize action code "%s"' % action_code)
    if prod_code not in products:
        raise RuntimeError('don\'t recognize product code "%s"' % prod_code)

    return {
        'action_code': action_code,
        'action': actions[action_code],
        'prod_code': prod_code,
        'product': products[prod_code],
    }

def validate_row(row, domain, data_cols):
    """pre-validate the information in a particular import row: valid location,
    reporting user, and data formats
    """
    # identify location
    loc_code = row.get('outlet_code') or row.get('site_code')
    row['loc'] = get_supply_point(domain, loc_code)['case']
    if row['loc'] is None:
        set_error(row, 'ERROR location code is invalid')
        return

    # identify user
    phone = row.get('phone')
    owner = None
    if phone:
        vn = VerifiedNumber.by_phone(phone)
        if not vn:
            set_error(row, 'ERROR phone number is not verified with any user')
            return
        owner = vn.owner
        row['phone'] = strip_plus(phone)

    username = row.get('reporter')
    if username:
        user = CouchUser.get_by_username('%s@%s.commcarehq.org' % (username, domain))
        if not user:
            set_error(row, 'ERROR reporter user does not exist')
            return

    if owner:
        if user and user._id != owner._id:
            set_error(row, 'ERROR phone number does not belong to user')
            return
        user = owner
    row['user'] = user

    # validate other fields

    try:
        row['timestamp'] = datetime.strptime(row['date'], '%Y-%m-%d') # TODO: allow time?
    except ValueError:
        set_error(row, 'ERROR invalid date format')
        return

    for k in data_cols:
        val = row[k]
        if val:
            try:
                int(val)
            except ValueError:
                set_error(row, 'ERROR invalid data value "%s" in column "%s"' % (val, k))
                return

    if all(not row[k] for k in data_cols):
        set_error(row, 'ERROR stock report is empty')
        return

def process_loc(domain, loc, rows, data_cols):
    """process (import) all the stock reports for a given location"""

    # get actual loc object
    loc = rows[0]['loc']

    # get date of latest-submitted stock report for this loc
    static_loc_id = loc.location_[-1]
    startkey = [domain, static_loc_id]
    endkey = list(startkey)
    endkey.append({})

    most_recent_entry = get_db().view('commtrack/stock_reports', startkey=endkey, endkey=startkey, descending=True).first()
    if most_recent_entry:
        most_recent_timestamp = most_recent_entry['key'][-1]
        most_recent_timestamp = datetime.strptime(most_recent_timestamp[:10], '%Y-%m-%d') # truncate to just date for now; also, time zone issues
    else:
        most_recent_timestamp = None

    if most_recent_timestamp:
        for row in rows:
            if row['timestamp'] <= most_recent_timestamp:
                set_error(row, 'ERROR date must be AFTER the most recently received stock report for this location (%s)' % most_recent_timestamp.strftime('%Y-%m-%d'))

    if any(row.get('error') for row in rows):
        set_error_bulk(rows, 'SKIPPED because other rows for this location have errors')
        return

    rows.sort(key=lambda row: row['timestamp'])
    for row in rows:
        try:
            import_row(row, data_cols, domain)
            set_error(row, 'SUCCESS row imported')
        except Exception, e:
            notify_exception(None, 'error during bulk stock report import')
            set_error(row, 'ERROR during import: %s' % str(e))
            set_error_bulk(rows, 'SKIPPED remaining rows due to unexpected error')
            break

def import_row(row, data_cols, domain):
    """process (import) a single stock report row"""
    def get_data():
        for header, meta in data_cols.iteritems():
            val = row[header]
            if val is not None and val != '':
                yield {'action': meta['action'], 'product': meta['product'], 'value': int(val)}

    report = {
        'location': row['loc'],
        'timestamp': row['timestamp'],
        'user': row['user'],
        'phone': row.get('phone'),
        'transactions': list(get_data()),
    }
    sms.process(domain, report)

def annotate_csv(data, columns):
    """update the original import csv with the import result for each row"""
    headers = list(columns)
    headers.insert(0, 'error')

    f = StringIO()
    writer = csv.DictWriter(f, headers, extrasaction='ignore')
    writer.writerow(dict((h, 'STATUS' if h == 'error' else h) for h in headers))
    writer.writerows(data)
    return f.getvalue()

def import_locations(domain, f):
    config = CommtrackConfig.for_domain(domain)
    known_loc_types = config.known_supply_point_types

    data = list(csv.DictReader(f))
    for loc in data:
        for m in import_location(domain, loc, known_loc_types):
            yield m

def import_location(domain, loc, known_loc_types):
    def _loc(*args, **kwargs):
        return make_loc(domain, *args, **kwargs)

    def get_by_name(loc_name, loc_type, parent):
        # TODO: could cache the results of this for speed
        existing = Location.filter_by_type(domain, loc_type, parent)
        try:
            return [l for l in existing if l.name == loc_name][0]
        except IndexError:
            return None

    HIERARCHY_FIELDS = ('state', 'district', 'block')
    hierarchy = [(p, loc[p]) for p in HIERARCHY_FIELDS]

    # create parent hierarchy if it does not exist
    parent = None
    for anc_type, anc_name in hierarchy:
        child = get_by_name(anc_name, anc_type, parent)
        if not child:
            child = _loc(name=anc_name, location_type=anc_type, parent=parent)
            yield 'created %s %s' % (anc_type, anc_name)
        parent = child

    name = loc['outlet_name']
    # check if outlet already exists
    outlet = get_by_name(name, 'outlet', parent)
    if outlet:
        yield 'outlet %s exists; skipping...' % name
        return

    if 'outlet_code' in loc:
        loc['site_code'] = loc['outlet_code']
        del loc['outlet_code']

    outlet_props = dict(loc)
    for k in ('outlet_name',):
        del outlet_props[k]
    if 'outlet_type' in outlet_props:
        outlet_props['outlet_type'] = outlet_props['outlet_type'].strip()
        if outlet_props['outlet_type'] not in known_loc_types:
            yield 'fyi: type "%s" for outlet "%s" is not a known outlet type' % (outlet_props.get('outlet_type'), name)

    # check that sms code for outlet is unique
    code = loc['site_code']
    existing_loc = get_supply_point(domain, code)['location']
    if existing_loc:
        yield 'code %s for outlet %s already in use! outlet NOT created' % (code, name)
        return

    outlet = _loc(name=name, location_type='outlet', parent=parent, **outlet_props)
    make_supply_point(domain, outlet)
    yield 'created outlet %s' % name

def make_loc(domain, *args, **kwargs):
    loc = Location(domain=domain, *args, **kwargs)
    loc.save()
    return loc
