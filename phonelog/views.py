from datetime import datetime, date, timedelta
from dimagi.utils.web import render_to_response
from django.http import HttpResponse
from dimagi.utils.couch.database import get_db
import logging
import itertools
import re
from corehq.apps.domain.decorators import login_and_domain_required

GAP_THRESHOLD = 3 #minutes

def device_list(db, domain):
    device_times = db.view('phonelog/device_log_first_last',
                           group=True,
                           startkey=[domain],
                           endkey=[domain, {}],
                           stale='update_after')
    device_users = db.view('phonelog/device_log_users',
                           group=True,
                           startkey=[domain],
                           endkey=[domain, {}],
                           stale='update_after')

    dev_users = {}
    for row in device_users:
        dev_id = row['key'][1]
        user = row['key'][2]
        if dev_id not in dev_users:
            dev_users[dev_id] = set()
        dev_users[dev_id].add(user)

    devices = []
    for row in device_times:
        dev = {
            'id': row['key'][1],
            'first': parse_isodate(row['value'][0]),
            'last': parse_isodate(row['value'][1]),
        }
        try:
            dev['users'] = dev_users[dev['id']]
        except KeyError:
            dev['users'] = set()
        devices.append(dev)
    return devices

def overview_list(db, domain):
    devices = device_list(db, domain)
    entries = []
    for dev in devices:
        users = dev['users'] if dev['users'] else set([None])
        for u in users:
            entry = {
                'user': u,
                'device': dev['id'],
                'first': dev['first'],
                'last': dev['last'],
                'other_users': sorted(list(users - set([u]))),
#                'overlaps_with': set(),
            }
            entries.append(entry)

    entries.sort(key=lambda e: (0, e['user'].upper(), e['first']) if e['user'] else (1, e['first']))

#    for u in set(e['user'] for e in entries):
#        user_entries = filter(lambda e: e['user'] == u, entries)
#        for a, b in itertools.combinations(user_entries, 2):
#            pass

    return entries

@login_and_domain_required
def devices(request, domain, template='phonelog/devicelist.html', context=None):
    context = context or {}
    entries = overview_list(get_db(), domain)
    context.update({'entries': entries, 'domain': domain, 'is_tabular': True})
    return render_to_response(request, template, context)

@login_and_domain_required
def device_log(request, domain, device, template='phonelog/devicelogs.html', context=None):
    context = context or {}
    db = get_db()

    try:
        limit = int(request.GET.get('limit'))
    except Exception:
        limit = 1000

    try:
        skip = int(request.GET.get('skip'))
    except Exception:
        skip = 0

    logdata = db.view('phonelog/device_logs',
                      limit=limit, skip=skip, 
                      descending=True, endkey=[device], startkey=[device, {}],
                      stale='update_after')
    logdata = list(logdata)
    logdata.reverse()

    def valid_log_entry(row):
        return isinstance(row["value"], dict) and not \
            len(filter(lambda val: not isinstance(val, dict), row["value"].values()))
    
    logdata = filter(lambda l: valid_log_entry(l), logdata)
    
    num = len(logdata)
    more_prev = (num == limit)
    more_next = (skip > 0)
    overlap = 10
    earlier_skip = skip + (limit - overlap)
    later_skip = max(skip - (limit - overlap), 0)

    def pure_log_entry(row):
        entry = {}
        entry.update(row['value'])
        del entry['version']
        return entry

    def frozendict(d):
        return tuple(sorted(d.iteritems(), key=lambda (k, v): k))

    dup_index = db.view('phonelog/device_log_uniq', group=True,
                        keys=[[device, pure_log_entry(row)] for row in logdata],
                        stale='update_after')
    dup_index = dict((frozendict(row['key'][1]), row['value']) for row in dup_index)

    def get_short_version(version):
        match = re.search(' (?P<build>#[0-9]+) ', version)
        return match.group('build') if match else None

    def parse_logs(logdata):
        for row in logdata:
            recv_raw = row['key'][1]
            cur_row = {
                'rowtype': 'log',
                'recvd': parse_isodate(recv_raw),
                'date': parse_isodate(row['value']['@date']),
                'type': row['value']['type'],
                'msg': row['value']['msg'],
                'version': get_short_version(row['value']['version']),
                'full_version': row['value']['version'],
                'raw_entry': frozendict(pure_log_entry(row)),
            }

            first_recv = dup_index[cur_row['raw_entry']]
            cur_row['dup'] = (first_recv != recv_raw)
            cur_row['first_recv'] = first_recv if cur_row['dup'] else None

            yield cur_row

    def yield_dups(dups):
        total = len(dups['recs'])
        uniq = len(set(r['raw_entry'] for r in dups['recs']))

        yield {
            'rowtype': 'duphdr',
            'total': total,
            'uniq': uniq,
            'recv': parse_isodate(dups['recv']),
            'i': dups['i'],
        }

        for dup in dups['recs']:
            dup['dupgroup'] = dups['i']
            yield dup

    def process_logs(logdata):
        dups = None
        dup_i = 0

        for r in parse_logs(logdata):
            if not r['dup'] or (dups != None and r['first_recv'] != dups['recv']):
                if dups != None:
                    for dupr in yield_dups(dups):
                        yield dupr
                    dups = None

            if r['dup']:
                if dups == None:
                    dups = {'i': dup_i, 'recv': r['first_recv'], 'recs': []}
                    dup_i += 1
                dups['recs'].append(r)
            else:
                yield r

        if dups != None:
            for dupr in yield_dups(dups):
                yield dupr

    def fdelta(delta):
        return 86400.*delta.days + delta.seconds + 1.0e-6*delta.microseconds

    def format_timediff(s):
        s = int(abs(s)) + 30 #round to minute
        days = s / 86400
        hrs = (s / 3600) % 24
        mins = (s / 60) % 60
        secs = s % 60

        if days > 0:
            return '%dd %02dh %02dm' % (days, hrs, mins)
        elif hrs > 0:
            return '%dh %02dm' % (hrs, mins)
        else:
            return '%dm' % (mins)

    def annotate_logs(logdata):
        prev_row = None
        for r in process_logs(logdata):
            if r['rowtype'] == 'log' and not r['dup']:
                if prev_row and (prev_row['date'] > r['date'] or
                                 r['date'] - prev_row['date'] > timedelta(minutes=GAP_THRESHOLD)):
                    yield {
                        'rowtype': 'time',
                        'regress': (prev_row['date'] > r['date'] + timedelta(seconds=45)),
                        'fdiff': fdelta(r['date'] - prev_row['date']),
                        'diff': format_timediff(fdelta(r['date'] - prev_row['date'])),
                    }
                
                prev_row = r
            yield r

    context.update({
        'logs': annotate_logs(logdata),
        'limit': limit,
        'more_next': more_next,
        'more_prev': more_prev,
        'earlier_skip': earlier_skip,
        'later_skip': later_skip,
        'domain': domain,
        'device': device,
        'is_tabular': True
    })

    return render_to_response(request, template, context)

@login_and_domain_required
def device_log_raw(request, domain, device, template='phonelog/devicelogs_raw.html', 
                   context=None):
    
    logs = get_db().view("phonelog/device_log_first_last",
                         key=[domain, device], reduce=False,
                         stale='update_after')
    def fmt_log(log):
        return {"received_on": parse_isodate(log["value"]),
                "id": log["id"]}
    
    context.update({
        "domain": domain,
        "logs": sorted(map(fmt_log, logs), key=lambda log: log["received_on"], reverse=True),
        "device": device
    })
    
    return render_to_response(request, template, context)

def parse_isodate(datestr):
    return datetime.strptime(datestr[:19], '%Y-%m-%dT%H:%M:%S')
