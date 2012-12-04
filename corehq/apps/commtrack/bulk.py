import csv
from datetime import datetime
from models import *
from corehq.apps.sms.mixin import VerifiedNumber, strip_plus
from corehq.apps.locations.models import Location
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase
from dimagi.utils.couch.database import get_db

def import_stock_reports(domain, f):
    data = list(csv.DictReader(f))
    headers = reduce(lambda a, b: a.union(b.keys()), data, set())

    try:
        data_col_mapping = validate_headers(domain, headers)
    except Exception, e:
        yield str(e)
        return

    locs_by_id = dict((loc.outlet_id, loc) for loc in Location.filter_by_type(domain, 'outlet'))
    for row in data:
        validate_row(row, domain, data_col_mapping, locs_by_id)
 
    for i, row in enumerate(data):
        if 'error' in row:
            yield 'row %d: %s' % (i, row['error'])

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
    phone = row.get('phone')
    owner = None
    if phone:
        vn = VerifiedNumber.by_phone(phone)
        if not vn:
            row['error'] = 'phone number is not verified with any user'
            return
        owner = vn.owner
        row['phone'] = strip_plus(phone)

    username = row.get('reporter')
    if username:
        user = CouchUser.get_by_username('%s@%s.commcarehq.org' % (username, domain))
        if not user:
            row['error'] = 'reporter user does not exist'
            return

    if owner:
        if user and user._id != owner._id:
            row['error'] = 'phone number does not belong to user'
            return
        user = owner
    row['user'] = user

    loc_id = row.get('outlet_id')
    loc_code = row.get('outlet_code')
    loc_from_id, loc_from_code = None, None
    if loc_id:
        loc_from_id = locs_by_id.get(loc_id) # loc object
        if loc_from_id is None:
            row['error'] = 'location id is invalid'
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
            row['error'] = 'location code is invalid'
            return
    if loc_from_id and loc_from_code and loc_from_id._id != loc_from_code._id:
        row['error'] = 'location id and code refer to different locations'
        return
    row['loc'] = loc_from_code or loc_from_id

    try:
        datetime.strptime(row['date'], '%Y-%m-%d')
    except ValueError:
        row['error'] = 'invalid date format'
        return

    for k in data_cols:
        val = row[k]
        if val:
            try:
                int(val)
            except ValueError:
                row['error'] = 'invalid data value "%s" in column "%s"' % (val, k)
                return
