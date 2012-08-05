from copy import copy
import json
from celery.task.base import Task
from django.views.decorators.http import require_POST
import re
from django.http import HttpResponse
import restkit
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.groups.models import Group
from corehq.apps.migration import tasks
from corehq.apps.migration.post import post_data
from corehq.apps.migration.util import submission_xml
from corehq.apps.migration.util.submission_xml import prepare_for_resubmission
from corehq.apps.migration.add_user_id import add_user_id
from corehq.apps.migration.models import MigrationUser
from corehq.apps.receiverwrapper.util import get_submit_url
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.web import json_response, render_to_response
from receiver.util import spoof_submission


class UserMap(object):
    def __init__(self, domain, *args, **kwargs):
        #dict.__init__(self, *args, **kwargs)
        self.domain = domain
        self._cache = {}

    def __contains__(self, username):
        if username in self._cache:
            return True
        r = get_db().view('migration/user_id_by_username', key=[self.domain, username]).one()
        if r:
            user_id = r['value']
            self._cache[username] = user_id
            return True
        else:
            return False

    def __getitem__(self, username):
        if username in self._cache:
            return self._cache[username]
        r = get_db().view('migration/user_id_by_username', key=[self.domain, username]).one()
        if r:
            user_id = r['value']
            self._cache[username] = user_id
            return user_id
        else:
            raise KeyError()

    def __setitem__(self, username, user_id):
        u = MigrationUser()
        u.username = username
        u.domain = self.domain
        u.user_id = user_id
        u.save()
        self._cache[username] = user_id

    def get(self, k, d=None):
        return self[k] if k in self else d

def is_user_registration(xml):
    return re.search(r'openrosa.org/user-registration', xml)


def update_migration_users(xml, user_map):
    """Updates the database of users and returns whether it made an addition or not
    (It doesn't make an addition if the username/domain was already taken)"""
    def get_username(reg):
        username = re.search(r'<username>(.*)</username>', reg).group(1)
        return normalize_username(username)

    def get_user_id(reg):
        return re.search(r'<uuid>(.*)</uuid>', reg).group(1)

    username = get_username(xml)
    submit = username not in user_map
    if submit:
        user_id = get_user_id(xml)
        user_map[username] = user_id
    return submit

def post(request, domain):
    """expects same posts as receiver but munges the forms before passing them on"""

    xml = request.raw_post_data
    user_map = UserMap(domain)
    submit = True
    if is_user_registration(xml):
        submit = update_migration_users(xml, user_map)
    else:
        xml = add_user_id(xml, user_map)
    if submit:
        submit_time = request.META.get('HTTP_X_SUBMIT_TIME', None)
        headers = {"HTTP_X_SUBMIT_TIME": submit_time} if submit_time else {}
        return spoof_submission(get_submit_url(domain), xml, hqsubmission=False, headers=headers)
    else:
        return HttpResponse("user already exists")

# ---- July 2012 Bihar migration----

@require_superuser
def resubmit_for_users(request, domain):
    """
    url-base: "https://india.commcarehq.org/a/care-bihar"

    """
    if request.method == 'POST':
        data = json.loads(request.raw_post_data)
        async = data.get('async', False)
        debug = data.get('debug', False)
        check = data.get('check', False)
        url_base = data['url_base']
        app_id = data['app_id']
        remote_mapping = data['remote_mapping']
        # having this exposed was totally insecure...
#        def get_remote_id_mapping():
#            url = url_base + '/settings/api/id_mapping/'
#            response = restkit.request(url)
#            if response.status[0] == '2':
#                body = response.body_string()
#                return json.loads(body)
#            else:
#                raise Exception("Failure at %s" % url)
#
#        remote_mapping = get_remote_id_mapping()

        def get_id(type, origin, name):
            """
                i.e.
                get_id('users', 'remote', 'barbara')
            """
            if origin == 'remote':
                return remote_mapping[type][name]
            if (type, origin) == ('users', 'local'):
                username = normalize_username(name, domain)
                user = CommCareUser.get_by_username(username)
                if user:
                    return user.user_id
                else:
                    raise Exception('Unknown local user "%s"' % username)
            if (type, origin) == ('groups', 'local'):
                return Group.by_name(domain, name).get_id

        id_mapping = {}
        for type in 'users', 'groups':
            id_mapping[type] = dict([(get_id(type, 'local', local_name), get_id(type, 'remote', remote_name)) for (local_name, remote_name) in data[type].items()])

        args = url, user_id_mapping, group_id_mapping, domain = url_base + '/receiver/' + app_id + '/', id_mapping['users'], id_mapping['groups'], domain

        if debug:
            forms = []
            for form in tasks.forms_for_cases_for_users(id_mapping['users'].keys(), domain):
                new_xml = prepare_for_resubmission(form.get_xml(), copy(user_id_mapping), copy(group_id_mapping), salt=url)
#                if form.get_id in new_xml:
                forms.append({
                    'id': form.get_id,
                    'xml': form.get_xml(),
                    'new_xml': new_xml,
                    'submit_time': form.received_on,
                    'new_id': None
                })
            return json_response({
                'forms': forms,
                'user_id_mapping': user_id_mapping,
                'group_id_mapping': group_id_mapping,
            })
        elif check:
            forms = []
            for form in tasks.forms_for_cases_for_users(id_mapping['users'].keys(), domain):
                new_id = submission_xml.IdMap(url)(form.get_id)
                went_through = get_db().doc_exist(new_id)
                if not went_through:
                    new_xml = prepare_for_resubmission(form.get_xml(), copy(user_id_mapping), copy(group_id_mapping), salt=url)
                    forms.append({
                        'id': form.get_id,
                        'xml': form.get_xml(),
                        'new_id': new_id,
                        'new_xml': new_xml
                    })
            return json_response({
                'forms': forms,
                'user_id_mapping': user_id_mapping,
                'group_id_mapping': group_id_mapping,
                })
        else:
            if async:
                subtask = tasks.resubmit_for_users.delay(*args)
                return json_response({'task_id': subtask.task_id})
            else:
                tasks.resubmit_for_users(*args)
                return json_response(id_mapping)
    else:
        if request.GET.get('debug'):
            return render_to_response(request, 'migration/resubmit_for_users_debug.html', {
                'domain': domain
            })
        else:

            task_id = request.GET.get('task_id')
            if task_id:
                result = Task.AsyncResult(task_id)
                return json_response({'task_id': task_id, 'state': result.state, 'info': result.info})
            else:
                return render_to_response(request, 'migration/resubmit_for_users.html', {
                    'domain': domain
                })

@require_superuser
def forward(request, domain):
    data = json.loads(request.raw_post_data)
    xml = data['xml']
    url = data['url']
    submit_time = data['submit_time']
    results, errors = post_data(xml, url, submit_time=submit_time)
    return json_response({'results': results, 'errors': errors})