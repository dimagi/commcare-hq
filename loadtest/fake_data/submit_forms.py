import datetime, random, string
import os.path
from StringIO import StringIO

from django.test.client import RequestFactory
from django.template.loader import get_template_from_string
from django.template.context import Context

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
        self.name = "%s %s" % (random.choice(names)[0], random.choice(names)[2]),
        self.id = self.random_key(),

    def random_key():
        return '%s-%s-%s-%s-%s' % tuple([
            ''.join([random.choice(self.chars) for i in range(n)])
            for n in [8, 4, 4, 4, 12]
        ])

    @property
    def context():
        if self._context is None:
            self._context = {
                'name': self.name,
                'age': int(random.normalvariate(28, 10)),
                'lmp': self.lmp,  # last menstrual period
                'edd': self.lmp + datetime.timedelta(weeks=37),
                'case_id': self.case_id, 
                'user_id': user._id,  # base username?
                'username': user.username,
                'date_modified': self.submitted.date(),
                'device_id': ''.join([random.choice(self.chars) for i in range(26)]),
                # 2013-07-09T11:09:28.361-04
                'time_start': self.submitted - datetime.timedelta(minutes=random.randint(1,60)),
                'time_end': self.submitted,
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
    return rcv_views.post(req, domain)


def make_forms(domain, app_id, user, num_new, updates_per_case=None):
    """
    make `num_new` new forms and `num_updates` updates to those new forms (randomized)
    """
    url_path = '/a/%s/receiver/%s' % (domain, app_id)
    case_ids = []
    for i in range(num_new):
        form = NewCaseForm(user)
        case_ids.append(form.case_ids)
        submit_xform(url_path, domain, form.render(),
               {'HTTP_X_SUBMIT_TIME': form.submitted})
        print form.id

    for case_id in case_ids:
        for i in range(random.randint(0, updates_per_case*2)):
            form = UpdateCaseForm(user, case_id)
            submit_xform(url_path, domain, form.render(),
                   {'HTTP_X_SUBMIT_TIME': form.submitted})


