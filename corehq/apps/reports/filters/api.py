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
        # user_options = [("u__%s" % u.get_id, "%s [user]" % u.name_in_filters)
                # for u in user_list(self.domain)]
        group_options = [("g__%s" % g.get_id, "%s [group]" % g.name)
                for g in Group.get_reporting_groups(self.domain)]
        options = all_workers + user_types + group_options
        options += self.get_users()
        return [{'id': id, 'text': text} for id, text in options]

    # TODO: sort this
    def get_users(self):
        fields = ['_id', 'username', 'first_name', 'last_name']
        users = es_wrapper('users', domain=self.domain, doc_type='CommCareUser',
            fields=fields, size=10)
        def user_tuple(u):
            user = _report_user_dict(u)
            uid = "u__%s" % user['user_id']
            name = user['username_in_report']
            return (uid, name)
        return map(user_tuple, users)

        # return [(u['user_id'], u['username_in_report'])
            # for u in map(_report_user_dict, users)]

    def get_groups(self):
        pass
