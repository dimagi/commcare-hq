import csv
from StringIO import StringIO
from datetime import datetime
from models import *
from corehq.apps.sms.mixin import VerifiedNumber, strip_plus
from corehq.apps.locations.models import Location
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.loosechange import map_reduce

def set_error(row, msg, override=False):
    if override or 'error' not in row:
        row['error'] = msg

def set_error_bulk(rows, msg, override=False):
    for row in rows:
        set_error(row, msg, override)

def import_stock_reports(domain, f):
    reader = csv.DictReader(f)
    data = list(reader)
    headers = reduce(lambda a, b: a.union(b.keys()), data, set())

    try:
        data_col_mapping = validate_headers(domain, headers)
    except Exception, e:
        raise RuntimeError(str(e))

    locs_by_id = dict((loc.outlet_id, loc) for loc in Location.filter_by_type(domain, 'outlet'))
    for row in data:
        validate_row(row, domain, data_col_mapping, locs_by_id)

    # abort if any location codes are invalid
    if any(not row.get('loc') for row in data):
        set_error_bulk(data, 'SKIPPED because some rows could not be assigned to a valid location')
    
    else:

        rows_by_loc = map_reduce(lambda row: [(row['loc']._id,)], data=data, include_docs=True)
        for loc, rows in rows_by_loc.iteritems():
            process_loc(domain, loc, rows)

    return annotate_csv(data, reader.fieldnames)
    
def validate_headers(domain, headers):
    META_COLS = ['outlet_id', 'outlet_code', 'date', 'reporter', 'phone']

    if 'reporter' not in headers and 'phone' not in headers:
        raise RuntimeError('"reporter" or "phone" column required')
    if 'outlet_id' not in headers and 'outlet_code' not in headers:
        raise RuntimeError('"outlet_id" or "outlet_code" column required')
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
        
    return (action_code, prod_code)

def validate_row(row, domain, data_cols, locs_by_id):
    # identify location
    loc_id = row.get('outlet_id')
    loc_code = row.get('outlet_code')
    loc_from_id, loc_from_code = None, None
    if loc_id:
        loc_from_id = locs_by_id.get(loc_id) # loc object
        if loc_from_id is None:
            set_error(row, 'ERROR location id is invalid')
            return
        # convert location to supply point case
        case_id = [case for case in loc_from_id.linked_docs('CommCareCase') if case['type'] == 'supply-point'][0]['_id']
        loc_from_id = CommCareCase.get(case_id)
    if loc_code:
        loc_code = loc_code.lower()
        loc_from_code = CommCareCase.view('commtrack/locations_by_code',
                                          key=[domain, loc_code],
                                          include_docs=True).first()
        if loc_from_code is None:
            set_error(row, 'ERROR location code is invalid')
            return
    if loc_from_id and loc_from_code and loc_from_id._id != loc_from_code._id:
        set_error(row, 'ERROR location id and code refer to different locations')
        return
    row['loc'] = loc_from_code or loc_from_id

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
        datetime.strptime(row['date'], '%Y-%m-%d')
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

def process_loc(domain, loc, rows):
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
        most_recent_timestamp = most_recent_timestamp[:10] # truncate to just date for now; also, time zone issues

    if most_recent_timestamp:
        for row in rows:
            if row['date'] <= most_recent_timestamp:
                set_error(row, 'ERROR date must be AFTER the most recently received stock report for this location (%s)' % most_recent_timestamp)

    if any(row.get('error') for row in rows):
        set_error_bulk(rows, 'SKIPPED because other rows for this location have errors')
        return

    rows.sort(key=lambda row: row['date'])
    for row in rows:
        try:
            import_row(row)
            set_error(row, 'SUCCESS row imported')
        except Exception, e:
            set_error(row, 'ERROR during import: %s' % str(e))
            set_error_bulk(rows, 'SKIPPED remaining rows due to unexpected error')
            break

def import_row(row):
    pass

    # generate the data dict that sms.StockReport.parse() makes
    #   import

def annotate_csv(data, columns):
    headers = list(columns)
    headers.insert(0, 'error')

    f = StringIO()
    writer = csv.DictWriter(f, headers, extrasaction='ignore')
    writer.writerow(dict((h, 'STATUS' if h == 'error' else h) for h in headers))
    writer.writerows(data)
    return f.getvalue()
