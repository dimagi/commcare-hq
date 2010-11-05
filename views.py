from datetime import datetime, date, timedelta
from bhoma.utils.render_to_response import render_to_response
from django.http import HttpResponse
from bhoma.utils.couch.database import get_db
import logging
import itertools
import re

def device_list(db):
    device_times = db.view('phonelog/device_log_first_last', group=True)
    device_users = db.view('phonelog/device_log_users', group=True)

    dev_users = {}
    for row in device_users:
        dev_id = row['key'][0]
        user = row['key'][1]
        if dev_id not in dev_users:
            dev_users[dev_id] = set()
        dev_users[dev_id].add(user)

    devices = []
    for row in device_times:
        dev = {
            'id': row['key'],
            'first': datetime.utcfromtimestamp(row['value'][0]),
            'last': datetime.utcfromtimestamp(row['value'][1]),
        }
        try:
            dev['users'] = dev_users[dev['id']]
        except KeyError:
            dev['users'] = set()
        devices.append(dev)
    return devices

def overview_list(db):
    devices = device_list(db)
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

def devices(request):
    entries = overview_list(get_db())
    return render_to_response(request, 'phonelog/devicelist.html', {'entries': entries})

def device_log(request, device):
    db = get_db()

    try:
        limit = int(request.GET.get('limit'))
    except:
        limit = 1000

    try:
        skip = int(request.GET.get('skip'))
    except:
        skip = 0

    logdata = db.view('phonelog/device_logs',
                      limit=limit, skip=skip, 
                      descending=True, endkey=[device], startkey=[device, {}])
    logdata = list(logdata)
    logdata.reverse()

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
                        keys=[[device, pure_log_entry(row)] for row in logdata])
    dup_index = dict((frozendict(row['key'][1]), row['value']) for row in dup_index)
    print list(dup_index)

    def get_short_version(version):
        match = re.search(' (?P<build>#[0-9]+) ', version)
        return match.group('build') if match else None

    def parse_logs(logdata):
        prev_row = None

        for i, row in enumerate(logdata):
            recv_raw = row['key'][1]
            cur_row = {
                'rowtype': 'log',
                'recvd': datetime.utcfromtimestamp(recv_raw),
                'date': datetime.strptime(row['value']['@date'][:19], '%Y-%m-%dT%H:%M:%S'),
                'type': row['value']['type'],
                'msg': row['value']['msg'],
                'version': get_short_version(row['value']['version']),
                'full_version': row['value']['version'],
                'raw_entry': frozendict(pure_log_entry(row)),
            }

            if prev_row and prev_row['date'] > cur_row['date']:
                cur_row['time_discrepancy'] = True

            first_recv = dup_index[cur_row['raw_entry']]
            cur_row['dup'] = (first_recv != recv_raw)
            cur_row['first_recv'] = first_recv if cur_row['dup'] else None

            yield cur_row
            prev_row = cur_row

    def yield_dups(dups):
        total = len(dups['recs'])
        uniq = len(set(r['raw_entry'] for r in dups['recs']))

        yield {
            'rowtype': 'duphdr',
            'total': total,
            'uniq': uniq,
            'recv': datetime.utcfromtimestamp(dups['recv']),
            'i': dups['i'],
        }

        for dup in dups['recs']:
            dup['dupgroup'] = dups['i']
            yield dup

    def process_logs(logata):
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

    return render_to_response(request, 'phonelog/devicelogs.html', {
        'logs': process_logs(logdata),
        'limit': limit,
        'more_next': more_next,
        'more_prev': more_prev,
        'earlier_skip': earlier_skip,
        'later_skip': later_skip,
    })
