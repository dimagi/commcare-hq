import urllib2
import json
import random
import math
from datetime import datetime, date, timedelta
import time
import threading
import sys
from optparse import OptionParser
import os
import os.path
from StringIO import StringIO
import logging
import logging.handlers

#how often to click the 'back' button
BACK_FREQ = .05

#how often to answer with blank
BLANK_FREQ = .1

#how often to give a knowingly out-of-range answer (for
#most questions we don't know the allowed range)
OUT_OF_RANGE_FREQ = .1

#relative frequencies of repeat actions
REPEAT_FREQ = {
    'edit': .2,
    'delete': .1,
    'done': .1,
    'add': .6,
}

MIN_DELAY = .01 #s
VALIDATION_BACKOFF = .25

def request(server, payload):
    conn = urllib2.urlopen('http://' + server, json.dumps(payload))
    return json.loads(conn.read())

def monkey_loop(form_id):
    def r(resp):
        if resp.get('event'):
            return (resp, resp['event'], resp['event']['type'])
        else:
            return (resp, evt, evt_type)

    resp, evt, evt_type = r((yield ('new-form', {'form-name': form_id})))

    while evt_type != 'form-complete':
        if random.random() < BACK_FREQ:
            resp, evt, evt_type = r((yield ('back', {})))

        if evt_type == 'question':
            answer = random_answer(evt['datatype'], len(evt['choices']) if evt.get('choices') else None)
            resp, evt, evt_type = r((yield ('answer', {'answer': answer})))
        elif evt_type == 'repeat-juncture':
            resp, evt, evt_type = r((yield repeat_juncture(evt)))

def random_answer(datatype, num_choices):
    if random.random() < BLANK_FREQ:
        return None

    # not used yet
    in_range = (random.random() > OUT_OF_RANGE_FREQ)

    if datatype == 'int':
        return random.randint(0, 100)
    elif datatype == 'float':
        return round(100 * random.random(), random.randint(0, 4))
    elif datatype == 'str':
        numeric = (random.random() < .2)
        alphabet = '0123456789' if numeric else 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ        '
        return ''.join(random.choice(alphabet) for i in range(random.randint(3, 12)))
    elif datatype == 'date':
        # before, after
        future = (random.random() < .1)
        params = (25500, 60) if not future else (-1000, 10)
        return rand_date(*params).strftime('%Y-%m-%d')
    elif datatype == 'time':
        return '%02d:%02d' % (random.randint(0, 23), random.randint(0, 59))
    elif datatype == 'select':
        return random.randint(1, num_choices)
    elif datatype == 'multiselect':
        # as-select1
        how_many = [(i, 1./i**.5) for i in range(1, num_choices + 1)]
        how_many.append((0, .3))
        return random.sample(xrange(1, num_choices + 1), choose_weighted(how_many))

def rand_date(max_range, max_rel_likelihood):
    return date.today() + timedelta(days=exp_dist(-max_range, max_rel_likelihood))

def exp_dist(max_range, max_rel_resolution):
    exp_max = math.log(max_rel_resolution)
    k = exp_max * random.random()
    return (math.exp(k) - 1.) / (max_rel_resolution - 1.) * max_range

def choose_weighted(choices):
    total = sum(ch[1] for ch in choices)
    r = random.random() * total
    for choice, weight in choices:
        if r < weight:
            return choice
        else:
            r -= weight

def repeat_juncture(evt):
    actions = REPEAT_FREQ.copy()
    num_reps = len(evt['repetitions'])

    if not evt['add-choice']:
        del actions['add']
    if not evt['del-choice'] or num_reps == 0:
        del actions['delete']
    if num_reps == 0:
        del actions['edit']

    action = choose_weighted(actions.items())
    if action == 'done':
        return ('next', {})
    elif action == 'add':
        return ('new-repeat', {})
    elif action == 'edit':
        return ('edit-repeat', {'ix': random.randint(1, num_reps)})
    elif action == 'delete':
        return ('delete-repeat', {'ix': random.randint(1, num_reps)})

def run_monkey(g, server_url, avg_delay):
    session_id = None

    def mk_payload(action, args):
        payload = args.copy()
        payload['action'] = action
        if session_id:
            payload['session-id'] = session_id
        return payload

    try:
        resp = None
        req = None
        validation_fail_count = 0
        while True:
            action, args = (g.send(resp) if req is None else req)
            log('<< %s %s' % (action, str(args)))
            resp = request(server_url, mk_payload(action, args))
            log('>> %s' % str(resp))

            if not session_id:
                session_id = resp['session_id']

            #handle form nav steps that are completely non-interactive
            req = None
            if resp.get('event') and resp['event']['type'] == 'sub-group':
                req = ('next', {})

            #keep track of how many times the validation has failed, and speed
            #things up if so
            if resp.get('status') and resp['status'] != 'accepted':
                validation_fail_count += 1
            else:
                validation_fail_count = 0

            delay = calc_delay(avg_delay)
            #this doesn't work as planned because the 'back' action resets the counter
            delay *= math.exp(-validation_fail_count * VALIDATION_BACKOFF)
            sleep(delay)

    except StopIteration:
        return resp['event']['output']

def calc_delay(avg_delay, std_dev=None):
    if std_dev == None:
        std_dev = .4 * avg_delay
    return max(random.normalvariate(avg_delay, std_dev), 0.)

def log(msg, level=logging.DEBUG):
    thread_tag = threading.current_thread().tag
    logging.log(level, '%s %s' % (thread_tag, msg))

def hash_tag(len):
    return '%0*x' % (len, random.randint(0, 16**len - 1))

def pretty_xml(raw):
    try:
        import lxml.etree as etree
    except ImportError:
        return raw

    return etree.tostring(etree.parse(StringIO(raw)), pretty_print=True)

class runner(threading.Thread):
    def __init__(self, server_url, form_id, delay, output_dir, delay_start=False):
        threading.Thread.__init__(self)
        self.tag = hash_tag(5)
        self.clock = 0

        self.server_url = server_url
        self.form_id = form_id
        self.delay = delay
        self.output_dir = output_dir
        self.delay_start = delay_start

    def run(self):
        try:
            if self.delay_start:
                self.sleep(random.random() * 2. * self.delay)

            output = run_monkey(monkey_loop(self.form_id), self.server_url, self.delay)

            if self.output_dir is None:
                print output
            else:
                filename = os.path.join(self.output_dir, '%s.%s.xml' % (datetime.now().strftime('%Y%m%d%H%M%S'), hash_tag(5)))
                with open(filename, 'w') as f:
                    f.write(pretty_xml(output))
                log('wrote to %s' % filename, logging.INFO)
        except:
            logging.exception('unexpected')

    def sleep(self, delay):
        if delay > 0:
            log('pause %1.5s' % delay)

        self.clock += delay
        if self.clock > MIN_DELAY:
            sleep_for = self.clock - self.clock % MIN_DELAY
            self.clock -= sleep_for
            time.sleep(sleep_for)

def sleep(delay):
    threading.current_thread().sleep(delay)

def initialize_logging(loginitfunc):
    """call in settings.py after importing localsettings to initialize logging.
    ensures that logging is only initialized once. 'loginitfunc' actually does
    the initialization"""
    if not hasattr(logging, '_initialized'):
        loginitfunc()
        logging.info('logging initialized')
        logging._initialized = True

def config_logging(logfile):
    """standard logging configuration useful for development. this should be
    the default argument passed to initialize_logging in settings.py. it should
    be overridden with a different function in localsettings.py when in a
    deployment environment"""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    h1 = logging.StreamHandler()
    h1.setLevel(logging.DEBUG)
    h1.setFormatter(logging.Formatter('%(message)s'))
    root.addHandler(h1)

    h2 = logging.handlers.RotatingFileHandler(logfile, maxBytes=2**24, backupCount=3)
    h2.setLevel(logging.ERROR)
    h2.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
    root.addHandler(h2)


if __name__ == "__main__":

    ERR_LOG = '/tmp/xformmonkey.err.log'
    DEFAULT_DELAY = 1.

    initialize_logging(lambda: config_logging(ERR_LOG))

    parser = OptionParser(usage='usage: %prog [options] xforms (files or directories containing solely xforms)')
    parser.add_option("-s", "--server", dest="server", default='127.0.0.1:4444',
                      help="touchforms server", metavar="SERVER")
    parser.add_option("-c", "--sessions", dest="sessions", default=1, type="int",
                      help="number of concurrent sessions", metavar="#CONCURRENT")
    parser.add_option("-n", "--total", dest="total", default=0, type="int",
                      help="total number of forms to generate", metavar="#FORMS")
    parser.add_option("-d", "--delay", dest="delay", type="float",
                      help="average delay between actions", metavar="DELAY")
    parser.add_option("-o", "--output", dest="outdir",
                      help="output directory for generated forms ('-' for stdout)", metavar="OUTPUTDIR")
    (opt, args) = parser.parse_args()

    if opt.sessions < 1:
        raise ValueError('# sessions must be >= 1')
    if opt.total < 0:
        raise ValueError('total # of forms must be >= 0')

    if opt.delay is None:
        opt.delay = DEFAULT_DELAY if opt.sessions > 1 else 0.
    elif opt.delay < 0:
        raise ValueError('delay must be non-negative')
    if opt.outdir == '-':
        opt.outdir = None

    forms = []
    for arg in args:
        path = os.path.normpath(os.path.join(os.getcwd(), arg))
        if not os.path.exists(path):
            raise ValueError('%s doesn\'t exist' % path)
        elif os.path.isdir(path):
            for sub in os.listdir(path):
                subpath = os.path.join(path, sub)
                if os.path.isfile(subpath):
                    # assume all files in the dir are xforms!
                    forms.append(subpath)
        else:
            forms.append(path)    
    if len(forms) == 0:
        raise ValueError('specify one or more forms')

    total_count = 0
    threads = []
    while opt.total == 0 or total_count < opt.total:
        threads = [th for th in threads if th.is_alive()]
        while len(threads) < opt.sessions:
            th = runner(opt.server, random.choice(forms), opt.delay, opt.outdir, True)
            threads.append(th)
            total_count += 1
            th.start()
        time.sleep(.01)
