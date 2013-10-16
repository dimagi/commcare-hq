import datetime, random, string
import os.path
from StringIO import StringIO

from django.test.client import Client
from django.test.client import RequestFactory
from django.template.loader import get_template_from_string
from django.template.context import Context

from dimagi.utils.parsing import json_format_datetime
from corehq.apps.receiverwrapper import views as rcv_views

from .names import names


def get_template(filename):
    filepath = os.path.join(os.path.dirname(__file__), 'xml', filename)
    with open(filepath) as file:
        raw = file.read()
    return get_template_from_string(raw)


new_case_template = get_template('new_case.xml')
update_case_template = get_template('update_case.xml')


class Form(object):
    chars = list(string.uppercase + '1234567890')
    _context = None

    def __init__(self, user, case_id=None):
        now = datetime.datetime.now()
        self.submitted = now - datetime.timedelta(days=random.randint(1,180))
        self.lmp = self.submitted.date() - datetime.timedelta(days=random.randint(1,60))
        self.user = user
        self.case_id = case_id or self.random_key()
        self.name = "%s %s" % (random.choice(names)[0], random.choice(names)[2])
        self.id = self.random_key()

    def random_key(self):
        return '%s-%s-%s-%s-%s' % tuple([
            ''.join([random.choice(self.chars) for i in range(n)])
            for n in [8, 4, 4, 4, 12]
        ])

    @property
    def context(self):
        if self._context is None:
            self._context = {
                'name': self.name,
                'age': int(random.normalvariate(28, 10)),
                'lmp': self.lmp.strftime('%Y-%m-%dT%H:%M:%SZ'),  # last menstrual period
                'edd': (self.lmp + datetime.timedelta(weeks=37)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'case_id': self.case_id, 
                'user_id': self.user._id,  # base username?
                'username': self.user.username,
                'date_modified': self.submitted.date().strftime('%Y-%m-%d'),
                'device_id': ''.join([random.choice(self.chars) for i in range(26)]),
                # 2013-07-09T11:09:28.361-04
                'time_start': (self.submitted - datetime.timedelta(minutes=random.randint(1,60))
                    ).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'time_end': self.submitted.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'instance_id': self.id, 
            }
            self._context.update(self.additional_context())
        return self._context

    def additional_context(self):
        return {}

    def render(self):
        return new_case_template.render(Context(self.context))


class NewCaseForm(Form):
    pass


class UpdateCaseForm(Form):
    def additional_context(self):
        boolean = lambda: random.choice(['yes', 'no'])
        return {
            'iron': boolean,
            'institutional': boolean,
            'tetanus_2': boolean,
            'tetanus_1': boolean,
            'prepared': boolean,
            'registration': boolean,
            'nutrition': boolean,
        }


def submit_xform(url_path, domain, submission_xml_string, extra_meta=None):
    """
    RequestFactory submitter
    """
    rf = RequestFactory()
    f = StringIO(submission_xml_string.encode('utf-8'))
    f.name = 'form.xml'

    req = rf.post(url_path, data={'xml_submission_file': f}) #, content_type='multipart/form-data')
    if extra_meta:
        req.META.update(extra_meta)
        req.domain = domain
    return rcv_views.post(req, domain)


# If you use multipart/form-data, please name your file xml_submission_file.
# You may also do a normal (non-multipart) post with the xml submission as the request body instead.
# Vary: Accept-Language, Cookie
# Content-Type: text/html; charset=utf-8
# Content-Language: en-us
# HTTP_X_OPENROSA_VERSION: 1.0

def make_forms(domain, app_id, user, cases, avg_updates=None):
    """
    make `cases` new cases each averaging `avg_updates` updates
    """
    client = Client()
    url_path = '/a/%s/receiver/%s/' % (domain, app_id)
    global last
    last = datetime.datetime.utcnow()

    def submit_form(form):
        global last
        now = datetime.datetime.utcnow()
        print "elapsed: %s" % (now-last)
        last = now
        f = StringIO(form.render().encode('utf-8'))
        f.name = "tempfile.xml"
        kwargs = dict(HTTP_X_SUBMIT_TIME=json_format_datetime(form.submitted))
        response = client.post("/a/{domain}/receiver/".format(domain=domain), {
            'xml_submission_file': f,
        }, **kwargs)
        # print response

    # make new cases
    case_ids = []
    for i in range(cases):
        form = NewCaseForm(user)
        case_ids.append(form.case_id)
        submit_form(form)

    # submit updates to cases
    for case_id in case_ids:
        for i in range(random.randint(0, avg_updates*2)):
            form = UpdateCaseForm(user, case_id)
            submit_form(form)

