import csv
from StringIO import StringIO
from datetime import datetime
from corehq.apps.commtrack.models import *
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.util import strip_plus
from corehq.apps.users.models import CouchUser
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.commtrack import sms
from dimagi.utils.logging import notify_exception
from corehq.apps.commtrack.util import get_supply_point
from django.utils.translation import ugettext as _
from soil import DownloadBase


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


def import_products(domain, download, task):
    messages = []
    products = []
    data = download.get_content().split('\n')
    processed = 0
    total_rows = len(data) - 1
    reader = csv.DictReader(data)
    for row in reader:
        try:
            p = Product.from_csv(row)
            if p:
                if p.domain:
                    if p.domain != domain:
                        messages.append(
                            _("Product {product_name} belongs to another domain and was not updated").format(
                                product_name=p.name
                            )
                        )
                        continue
                else:
                    p.domain = domain
                products.append(p)
            if task:
                processed += 1
                DownloadBase.set_progress(task, processed, total_rows)
        except Exception, e:
            messages.append(str(e))
    if products:
        Product.get_db().bulk_save(products)
        messages.insert(0, _('Successfullly updated {products} products with {errors} errors.').format(
            products=len(products), errors=len(messages))
        )
    return messages


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

    # TODO potential source of slowness
    most_recent_entry = get_db().view(
        'commtrack/stock_reports',
        startkey=endkey,
        endkey=startkey,
        descending=True,
        limit=1,
    ).first()
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

    make_tx = sms.transaction_factory(loc, StockTransaction)

    rows.sort(key=lambda row: row['timestamp'])
    for row in rows:
        try:
            import_row(row, data_cols, domain, make_tx)
            set_error(row, 'SUCCESS row imported')
        except Exception, e:
            notify_exception(None, 'error during bulk stock report import')
            set_error(row, 'ERROR during import: %s' % str(e))
            set_error_bulk(rows, 'SKIPPED remaining rows due to unexpected error')
            break

def import_row(row, data_cols, domain, make_tx):
    """process (import) a single stock report row"""
    def get_data():
        for header, meta in data_cols.iteritems():
            val = row[header]
            if val is not None and val != '':
                yield make_tx(domain=domain, action_name=meta['action'], product=meta['product'], value=int(val))

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

