import json
from couchdbkit import ResourceNotFound

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseBadRequest, HttpResponseRedirect, Http404
from django.utils.decorators import method_decorator
from django.views.generic.base import TemplateView
from django.shortcuts import render

from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.groups.models import Group
from corehq.apps.users.bulkupload import GroupMemoizer
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import CommCareUser, Permissions
from corehq.apps.users.util import normalize_username
from dimagi.utils.couch.bulk import CouchTransaction
from dimagi.utils.excel import WorkbookJSONReader, WorksheetNotFound
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response
from dimagi.utils.decorators.view import get_file


require_can_edit_fixtures = require_permission(Permissions.edit_data)

def strip_json(obj, disallow_basic=None, disallow=None):
    disallow = disallow or []
    if disallow_basic is None:
        disallow_basic = ['_rev', 'domain', 'doc_type']
    disallow += disallow_basic
    ret = {}
    try:
        obj = obj.to_json()
    except Exception:
        pass
    for key in obj:
        if key not in disallow:
            ret[key] = obj[key]

    return ret

def _to_kwargs(req):
    # unicode can mix this up so have a little utility to do it
    # was seeing this only locally, not sure if python / django
    # version dependent
    return dict((str(k), v) for k, v in json.load(req).items())

@require_can_edit_fixtures
def data_types(request, domain, data_type_id):
    
    if data_type_id:
        try:
            data_type = FixtureDataType.get(data_type_id)
        except ResourceNotFound:
            raise Http404()

        assert(data_type.doc_type == FixtureDataType._doc_type)
        assert(data_type.domain == domain)

        if request.method == 'GET':
            return json_response(strip_json(data_type))

        elif request.method == 'PUT':
            new = FixtureDataType(domain=domain, **_to_kwargs(request))
            for attr in 'tag', 'name', 'fields':
                setattr(data_type, attr, getattr(new, attr))
            data_type.save()
            return json_response(strip_json(data_type))

        elif request.method == 'DELETE':
            with CouchTransaction() as transaction:
                data_type.recursive_delete(transaction)
            return json_response({})

    elif data_type_id is None:

        if request.method == 'POST':
            data_type = FixtureDataType(domain=domain, **_to_kwargs(request))
            data_type.save()
            return json_response(strip_json(data_type))

        elif request.method == 'GET':
            return json_response([strip_json(x) for x in FixtureDataType.by_domain(domain)])

        elif request.method == 'DELETE':
            with CouchTransaction() as transaction:
                for data_type in FixtureDataType.by_domain(domain):
                    data_type.recursive_delete(transaction)
            return json_response({})

    return HttpResponseBadRequest()


def prepare_user(user):
    user.username = user.raw_username
    return strip_json(user, disallow=['password'])

@require_can_edit_fixtures
def data_items(request, domain, data_type_id, data_item_id):

    def prepare_item(item):
        ret = strip_json(item, disallow=['data_type_id'])
        if request.GET.get('groups') == 'true':
            ret['groups'] = []
            for group in item.get_groups():
                ret['groups'].append(strip_json(group))
        if request.GET.get('users') == 'true':
            ret['users'] = []
            for user in item.get_users():
                ret['users'].append(prepare_user(user))
        return ret

    if request.method == 'POST' and data_item_id is None:
        o = FixtureDataItem(domain=domain, data_type_id=data_type_id, **_to_kwargs(request))
        o.save()
        return json_response(strip_json(o, disallow=['data_type_id']))
    elif request.method == 'GET' and data_item_id is None:
        return json_response([
            prepare_item(x)
            for x in sorted(FixtureDataItem.by_data_type(domain, data_type_id),
                            key=lambda x: x.sort_key)
        ])
    elif request.method == 'GET' and data_item_id:
        try:
            o = FixtureDataItem.get(data_item_id)
        except ResourceNotFound:
            raise Http404()
        assert(o.domain == domain and o.data_type.get_id == data_type_id)
        return json_response(prepare_item(o))
    elif request.method == 'PUT' and data_item_id:
        original = FixtureDataItem.get(data_item_id)
        new = FixtureDataItem(domain=domain, **_to_kwargs(request))
        for attr in 'fields',:
            setattr(original, attr, getattr(new, attr))
        original.save()
        return json_response(strip_json(original, disallow=['data_type_id']))
    elif request.method == 'DELETE' and data_item_id:
        o = FixtureDataItem.get(data_item_id)
        assert(o.domain == domain and o.data_type.get_id == data_type_id)
        with CouchTransaction() as transaction:
            o.recursive_delete(transaction)
        return json_response({})
    else:
        return HttpResponseBadRequest()

def data_item_groups(request, domain, data_type_id, data_item_id, group_id):
    data_type = FixtureDataType.get(data_type_id)
    data_item = FixtureDataItem.get(data_item_id)
    group = Group.get(group_id)
    assert(data_type.doc_type == FixtureDataType._doc_type)
    assert(data_type.domain == domain)
    assert(data_item.doc_type == FixtureDataItem._doc_type)
    assert(data_item.domain == domain)
    assert(data_item.data_type_id == data_type_id)
    assert(group.doc_type == Group._doc_type)
    assert(group.domain == domain)

    if request.method == 'POST':
        data_item.add_group(group)
        return json_response({})
    elif request.method == 'DELETE':
        data_item.remove_group(group)
        return json_response({})
    else:
        return HttpResponseBadRequest()

def data_item_users(request, domain, data_type_id, data_item_id, user_id):
    data_type = FixtureDataType.get(data_type_id)
    data_item = FixtureDataItem.get(data_item_id)
    user = CommCareUser.get(user_id)
    assert(data_type.doc_type == FixtureDataType._doc_type)
    assert(data_type.domain == domain)
    assert(data_item.doc_type == FixtureDataItem._doc_type)
    assert(data_item.domain == domain)
    assert(data_item.data_type_id == data_type_id)
    assert(user.doc_type == CommCareUser._doc_type)
    assert(user.domain == domain)

    if request.method == 'POST':
        data_item.add_user(user)
        return json_response({})
    elif request.method == 'DELETE':
        data_item.remove_user(user)
        return json_response({})
    else:
        return HttpResponseBadRequest()

@require_can_edit_fixtures
def groups(request, domain):
    groups = Group.by_domain(domain)
    return json_response(map(strip_json, groups))

@require_can_edit_fixtures
def users(request, domain):
    users = CommCareUser.by_domain(domain)
    return json_response(map(prepare_user, users))

@require_can_edit_fixtures
def view(request, domain, template='fixtures/view.html'):
    return render(request, template, {
        'domain': domain
    })


class UploadItemLists(TemplateView):

    template_name = 'fixtures/upload_item_lists.html'

    def get_context_data(self, **kwargs):
        """TemplateView automatically calls this to render the view (on a get)"""
        return {
            'domain': self.domain
        }

    @method_decorator(get_file)
    def post(self, request):
        """View's dispatch method automatically calls this"""

        def error_redirect():
            return HttpResponseRedirect(reverse('upload_item_lists', args=[self.domain]))

        try:
            workbook = WorkbookJSONReader(request.file)
        except AttributeError:
            messages.error(request, "Error processing your Excel (.xlsx) file")
            return error_redirect()



        try:
            self._run_upload(request, workbook)
        except WorksheetNotFound as e:
            messages.error(request, "Workbook does not have a sheet called '%s'" % e.title)
            return error_redirect()
        except Exception as e:
            notify_exception(request)
            messages.error(request, "Fixture upload could not complete due to the following error: %s" % e)
            return error_redirect()

        return HttpResponseRedirect(reverse('fixture_view', args=[self.domain]))

    def _run_upload(self, request, workbook):
        group_memoizer = GroupMemoizer(self.domain)

        data_types = workbook.get_worksheet(title='types')

        def _get_or_raise(container, attr, message):
            try:
                return container[attr]
            except KeyError:
                raise Exception(message.format(attr=attr))
        with CouchTransaction() as transaction:
            for dt in data_types:
                err_msg = "Workbook 'types' has no column '{attr}'"
                data_type = FixtureDataType(
                    domain=self.domain,
                    name=_get_or_raise(dt, 'name', err_msg),
                    tag=_get_or_raise(dt, 'tag', err_msg),
                    fields=_get_or_raise(dt, 'field', err_msg),
                )
                transaction.save(data_type)
                data_items = workbook.get_worksheet(data_type.tag)
                for sort_key, di in enumerate(data_items):
                    data_item = FixtureDataItem(
                        domain=self.domain,
                        data_type_id=data_type.get_id,
                        fields=di['field'],
                        sort_key=sort_key
                    )
                    transaction.save(data_item)
                    for group_name in di.get('group', []):
                        group = group_memoizer.by_name(group_name)
                        if group:
                            data_item.add_group(group, transaction=transaction)
                        else:
                            messages.error(request, "Unknown group: %s" % group_name)
                    for raw_username in di.get('user', []):
                        username = normalize_username(raw_username, self.domain)
                        user = CommCareUser.get_by_username(username)
                        if user:
                            data_item.add_user(user)
                        else:
                            messages.error(request, "Unknown user: %s" % raw_username)
            for data_type in transaction.preview_save(cls=FixtureDataType):
                for duplicate in FixtureDataType.by_domain_tag(domain=self.domain, tag=data_type.tag):
                    duplicate.recursive_delete(transaction)


    @method_decorator(require_can_edit_fixtures)
    def dispatch(self, request, domain, *args, **kwargs):
        self.domain = domain
        return super(UploadItemLists, self).dispatch(request, *args, **kwargs)
