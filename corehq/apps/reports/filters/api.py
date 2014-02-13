"""
API endpoints for filter options
"""
from django.http import Http404, HttpResponseBadRequest, HttpResponse
from django.utils.translation import ugettext as _
from django.views.generic import View

from braces.views import JSONResponseMixin

from corehq.apps.groups.models import Group
from corehq.elastic import es_wrapper

from ..cache import CacheableRequestMixIn
from ..models import HQUserType
from ..util import _report_user_dict, user_list


# TODO: protect this view
class EmwfOptionsView(JSONResponseMixin, CacheableRequestMixIn, View):
    """
    Paginated options for the ExpandedMobileWorkerFilter
    """

    def get(self, request, domain):
        self.domain = domain
        self.q = self.request.GET.get('q', None)
        return self.render_json_response(self.get_options())

    def get_options(self):
        all_workers = [("_all_mobile_workers", _("[All mobile workers]"))]
        user_types = [("t__%s" % (i+1), "[%s]" % name)
                for i, name in enumerate(HQUserType.human_readable[1:])]
        options = all_workers + user_types
        options += self.get_groups()
        options += self.get_users()
        return [{'id': id, 'text': text} for id, text in options]

    def get_users(self):
        fields = ['_id', 'username', 'first_name', 'last_name']
        users = es_wrapper('users', domain=self.domain, doc_type='CommCareUser',
            fields=fields, start_at=0, size=10, sort_by='username', order='asc')
        def user_tuple(u):
            user = _report_user_dict(u)
            uid = "u__%s" % user['user_id']
            name = "%s [user]" % user['username_in_report']
            return (uid, name)
        return map(user_tuple, users)

    def get_groups(self):
        fields = ['_id', 'name']
        groups = es_wrapper('groups', domain=self.domain, doc_type='Group',
            fields=fields, start_at=0, size=10, sort_by='name', order='asc')
        return (("g__%s" % g['_id'], "%s [group]" % g['name'])
            for g in groups)
