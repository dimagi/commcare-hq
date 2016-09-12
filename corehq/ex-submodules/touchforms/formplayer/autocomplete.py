from __future__ import absolute_import

import itertools
import base64
import json
import time
import csv
import os.path
import threading
from django.core.cache import cache
from django.conf import settings
from touchforms.formplayer.util import get_autocomplete_dir

DEFAULT_NUM_SUGGESTIONS = 12

CACHE_TIMEOUT = 28800  #8 hrs -- essentially meant to be a static cache for one working day
CACHE_PREFIX_LEN = 3
DEFAULT_RES = .5

DATA_DIR = get_autocomplete_dir()

def func(funcname):
    path = funcname.split('.')
    package = '.'.join(path[:-1])
    method = path[-1]
    return getattr(__import__(package, fromlist=['*']), method)

def identity(x):
    return x

def groupby(it, keyfunc=identity, valfunc=identity, reducefunc=identity):
    grouped = {}
    for e in it:
        key = keyfunc(e)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(valfunc(e))
    return dict((k, reducefunc(vs)) for k, vs in grouped.iteritems())

def autocompletion(domain, key, max_results):
    if domain == 'firstname':
        return merge_autocompletes(max_results, *[get_autocompletion('firstname-%s' % gender, key, max_results) for gender in ('male', 'female')])

    return get_autocompletion(domain, key, max_results)

def merge_autocompletes(max_results, *responses):
    """combine the autocomplete responses from multiple domains"""
    response = {}
    responses = list(responses)

    all_suggestions = itertools.chain(*(r['suggestions'] for r in responses))
    grouped_suggestions = groupby(all_suggestions, lambda m: m['name'], lambda m: m['p'], sum)
    suggestions = [{'name': k, 'p': v} for k, v in grouped_suggestions.iteritems()]
    response['suggestions'] = sorted(suggestions, key=lambda m: -m['p'])[:max_results]

    hint_responses = [r['hinting'] for r in responses if 'hinting' in r]
    if hint_responses:
        freqs = [h['nextchar_freq'] for h in hint_responses]
        raw_freq_all = itertools.chain(*(fr.iteritems() for fr in freqs))
        freq_consolidated = groupby(raw_freq_all, lambda e: e[0], lambda e: e[1], sum)
        response['hinting'] = {'nextchar_freq': freq_consolidated}

        margins = [h['margin'] for h in hint_responses if 'margin' in h]
        if margins:
            response['hinting']['margin'] = max(margins)

    return response

def get_autocompletion(domain, key, maxnum):
    if cache_expired(domain):
        data = load_domain_data(domain)
        bg_init_cache(domain, data)

        #compute it on our own while the cache generates in background
        response = get_response(domain, key, data)

    else:
        response = cacheget((domain, 'results', key))
        if not response:
            #query is new and too deep; has not been cached yet
            rawdata = None
            lookup_key = key
            while rawdata == None and len(lookup_key) > 0:
                rawdata = cacheget((domain, 'raw', lookup_key))
                lookup_key = lookup_key[:-1]
            if rawdata == None:
                #prefix for which no matches exist
                rawdata = []
            response = get_response(domain, key, rawdata)

    response['suggestions'] = response['suggestions'][:maxnum]
    if response.get('hinting'):
        response['hinting']['margin'] = DOMAIN_CONFIG[domain].get('resolution', DEFAULT_RES)
    return response

def bg_init_cache(domain, data):
    def run():
        if cache_initializing(domain):
            return

        set_cache_initializing(domain, True)
        try:
            init_cache(domain, data)
        finally:
            set_cache_initializing(domain, False)

    threading.Thread(target=run).start()

def init_cache(domain, data):
    if data == None:
        data = load_domain_data(domain)

    for i in range(CACHE_PREFIX_LEN + 1):
        subdata = groupby(data, lambda e: e['name'][:i])
        for key, records in subdata.iteritems():
            #needed for very short names
            if len(key) != i:
                continue

            cacheset((domain, 'results', key), compute_autocompletion(records, key, DEFAULT_NUM_SUGGESTIONS))
            if i == CACHE_PREFIX_LEN:
                cacheset((domain, 'raw', key), records)
    set_cache_initialized(domain)

def get_response(domain, key, data):
    response = compute_autocompletion(data, key, DEFAULT_NUM_SUGGESTIONS)
    cacheset((domain, 'results', key), response)
    #todo: cache the subset of raw data as well?
    return response

def compute_autocompletion(data, key, maxnum, matchfunc=None):
    if matchfunc == None:
        matchfunc = lambda key, name: name.startswith(key)

    #autocomplete suggestions
    matches = []
    for d in data:
        if matchfunc(key, d['name']):
            matches.append(d)
            if len(matches) == maxnum:
                break

    #next-char statistics for keyboard hinting
    alpha = {}
    total = 0
    for d in data:
        if d['name'].startswith(key) and not d['name'] == key:
            c = d['name'][len(key)]
            if c not in alpha:
                alpha[c] = 0
            alpha[c] += d['p']
            total += d['p']

    return {'suggestions': matches, 'hinting': {'nextchar_freq': alpha}}

def load_domain_data(domain):
    config = DOMAIN_CONFIG[domain]
    data = []
    resolution = config.get('resolution', DEFAULT_RES)

    if config.get('static_file'):
        loadfunc = config['static_loader']
        data.extend(loadfunc(os.path.join(DATA_DIR, config.get('static_file'))))
        for e in data:
            if e['p'] is None:
                e['p'] = resolution

    if dynloadfunc:
        dyndata = list(dynloadfunc(domain, config.get('dynamic_inclusion_threshold')))
        for e in dyndata:
            e['p'] *= config.get('dynamic_bonus', 1.) * resolution
        data.extend(dyndata)

    for e in data:
        e['name'] = fixname(e['name'])

    data = [{'name': k, 'p': v} for k, v in groupby(data, lambda e: e['name'], lambda e: e['p'], sum).iteritems()]
    data.sort(key=lambda e: -e['p'])
    return data

def csv_loader(path, pcol=2, has_header=True):
    reader = csv.reader(open(path))
    if has_header:
        reader.next()
    for row in reader:
        sp = row[pcol - 1]
        yield {'name': row[0], 'p': float(sp) if sp else None}

#load data from US census name distribution files
def census_loader(path):
    with open(path) as f:
        lines = f.readlines()
        for ln in lines:
            name = ln[:15].strip()
            prob = float(ln[15:20]) / 100.
            yield {'name': name, 'p': prob}

def fixname(name):
    return name.strip().upper()

def cache_expired(domain):
    return cacheget(('meta', domain, 'initialized')) is None

def cache_initializing(domain):
    return cacheget(('meta', domain, 'initializing')) is not None

def set_cache_initializing(domain, status):
    if status:
        cacheset(('meta', domain, 'initializing'), True, 300)
    else:
        cachedel(('meta', domain, 'initializing'))

def set_cache_initialized(domain):
    cacheset(('meta', domain, 'initialized'), True, CACHE_TIMEOUT - 300)
    set_cache_initializing(domain, False)

### UTILITY FUNCTIONS FOR DEALING WITH MEMCACHED ###

def enc(data):
    return base64.b64encode(json.dumps(data))

def dec(data):
    return json.loads(base64.b64decode(data))

def cacheget(key):
    data = cache.get(enc(key))
    if data == None:
        return None
    else:
        return dec(data)

def cacheset(key, val, timeout=CACHE_TIMEOUT):
    cache.set(enc(key), enc(val), timeout)

def cachedel(key):
    cache.delete(enc(key))

### FUNCTIONS TO AID IN FUZZY MATCHING -- currently unused ###

def damerau_levenshtein_dist(s1, s2, thresh=9999):
    """compute the damerau-levenshtein distance between two strings"""
    if abs(len(s1) - len(s2)) > thresh:
        return None

    metric = compute_levenshtein(s1, s2, thresh)[-1][-1]
    return metric if metric <= thresh and metric >= 0 else None

def damlev_prefix_dist(prefix, target, thresh=9999):
    """compute the minimum damerau-levenshtein distance between target and all strings starting with prefix"""
    arr = compute_levenshtein(prefix, target, thresh, False)
    ixs = [k for k in arr[-1] if k >= 0]
    return min(ixs) if ixs else None

def munching_index_order(d1, d2, thresh):
    dmin = min(d1, d2)
    dmax = max(d1, d2)
    thresh = min(thresh, dmax)

    def ixround(a):
        for b in range(thresh):
            i = d1 - 1 - a
            j = d2 - 1 - a - thresh + b
            yield i, j

            i = d1 - 1 - a - thresh + b
            j = d2 - 1 - a
            yield i, j

        i = d1 - 1 - a
        j = d2 - 1 - a
        yield i, j

    for a in range(dmin - 1, -1, -1):
        yield [(i, j) for i, j in ixround(a) if i >= 0 and j >= 0]

def typewriter_index_order(d1, d2, thresh):
    for i in range(d1):
        yield [(i, j) for j in range(d2)]

def compute_levenshtein(s1, s2, thresh=9999, exact=True):
    d1 = len(s1) + 1
    d2 = len(s2) + 1
    arr = [[-1 for j in range(d2)] for i in range(d1)]

    def offset(i, j):
        return abs((d1 - d2) - (i - j)) if exact else 0

    def getarr(i, j):
        return arr[i][j] if offset(i, j) <= thresh else thresh + 1

    index_iterator = munching_index_order if exact else typewriter_index_order
    for ixround in index_iterator(d1, d2, thresh):
        for i, j in ixround:
            if i == 0:
                arr[i][j] = j
            elif j == 0:
                arr[i][j] = i
            else:
                cost = 0 if (s1[i - 1] == s2[j - 1]) else 1
                arr[i][j] = min(
                    getarr(i - 1, j) + 1,   #deletion
                    getarr(i, j - 1) + 1,   #insertion
                    getarr(i - 1, j - 1) + cost   #substitution
                )
                if i > 1 and j > 1 and (s1[i - 1], s1[i - 2]) == (s2[j - 2], s2[j - 1]):
                    arr[i][j] = min(
                        getarr(i, j),
                        getarr(i - 2, j - 2) + cost   #transposition
                    )

        if min(arr[i][j] + offset(i, j) for i, j in ixround) > thresh:
            break

    return arr

############33

def demo_config():
    return {
        'firstname-male': {
            'static_file': 'dist.male.first',
            'static_loader': census_loader,
            'resolution': 0.00001,
        },
        'firstname-female': {
            'static_file': 'dist.female.first',
            'static_loader': census_loader,
            'resolution': 0.00001,
        },
        'lastname': {
            'static_file': 'dist.all.last',
            'static_loader': census_loader,
            'resolution': 0.00001,
        },
        'village': {
            'static_file': 'usplaces.csv',
            'static_loader': csv_loader,
            'resolution': 200,
            'split': True,
        },
    }

try:
    configfunc = func(settings.TOUCHFORMS_AUTOCOMPL_CONFIGURATOR)
except AttributeError:
    configfunc = demo_config
DOMAIN_CONFIG = configfunc()

try:
    dynloadfunc = func(settings.TOUCHFORMS_AUTOCOMPL_DYNAMIC_LOADER)
except AttributeError:
    dynloadfunc = None
