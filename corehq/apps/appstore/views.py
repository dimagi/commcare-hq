import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from couchdbkit import ResourceNotFound
from memoized import memoized
from six.moves.urllib.parse import urlencode

from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.database import apply_update
from dimagi.utils.couch.resource_conflict import retry_resource
from dimagi.utils.logging import notify_exception
from dimagi.utils.name_to_url import name_to_url

from corehq.apps.accounting.models import SubscriptionAdjustmentMethod
from corehq.apps.accounting.tasks import ensure_explicit_community_subscription
from corehq.apps.app_manager.views.apps import clear_app_cache
from corehq.apps.appstore.exceptions import CopiedFromDeletedException
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.domain.exceptions import NameUnavailableException
from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import FixtureDataType
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq.elastic import (
    es_query,
    fill_mapping_with_facets,
    parse_args_for_es,
)

SNAPSHOT_FACETS = ['project_type', 'license', 'author.exact', 'is_starter_app']
SNAPSHOT_MAPPING = [
    ("", True, [
        {"facet": "project_type", "name": ugettext_lazy("Category"), "expanded": True},
        {
            "facet": "license",
            "name": ugettext_lazy("License"),
            "expanded": True,
            "mapping": {
                'cc': 'CC BY',
                'cc-sa': 'CC BY-SA',
                'cc-nd': 'CC BY-ND',
                'cc-nc': 'CC BY-NC',
                'cc-nc-sa': 'CC BY-NC-SA',
                'cc-nc-nd': 'CC BY-NC-ND',
            }
        },
        {"facet": "author.exact", "name": ugettext_lazy("Author"), "expanded": True},
    ]),
]


def rewrite_url(request, path):
    return HttpResponseRedirect('/exchange%s?%s' % (path, request.META['QUERY_STRING']))


def inverse_dict(d):
    return dict([(v, k) for k, v in d.items()])


def can_view_app(req, dom):
    if not dom or not dom.is_snapshot or not dom.published:
        return False
    if not dom.is_approved and (
        not getattr(req, "couch_user", "") or not req.couch_user.is_domain_admin(dom.copied_from.name)
    ):
        return False
    return True


def deduplicate(hits):
    unique_names = set()
    unique_hits = []
    for hit in hits:
        if not hit['_source']['name'] in unique_names:
            unique_hits.append(hit)
            unique_names.add(hit['_source']['name'])
    return unique_hits


class BaseCommCareExchangeSectionView(BaseSectionPageView):
    section_name = ugettext_lazy("CommCare Exchange")
    template_name = 'appstore/appstore_base.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if self.include_unapproved and not self.request.user.is_superuser:
            raise Http404()
        msg = """
            The CommCare Exchange is being retired in early December 2019.
            If you have questions or concerns, please contact <a href='mailto:{}'>{}</a>.
        """.format(settings.SUPPORT_EMAIL, settings.SUPPORT_EMAIL)
        messages.add_message(self.request, messages.ERROR, msg, extra_tags="html")
        return super(BaseCommCareExchangeSectionView, self).dispatch(request, *args, **kwargs)

    @property
    def include_unapproved(self):
        return self.request.GET.get('is_approved', "") == "false"

    @property
    def section_url(self):
        return reverse(CommCareExchangeHomeView.urlname)

    @property
    def page_url(self):
        return reverse(self.urlname)


class CommCareExchangeHomeView(BaseCommCareExchangeSectionView):
    urlname = 'appstore'

    @property
    def page_length(self):
        return 10

    @property
    @memoized
    def params(self):
        params, _ = parse_args_for_es(self.request)
        params.pop('page', None)
        return params

    @property
    def page(self):
        page = self.request.GET.get('page', 1)
        return int(page[0] if isinstance(page, list) else page)

    @property
    def sort_by(self):
        return self.request.GET.get('sort_by', None)

    @property
    def starter_apps(self):
        return self.request.GET.get('is_starter_app', None)

    @property
    def persistent_params(self):
        persistent_params = {}
        if self.sort_by:
            persistent_params["sort_by"] = self.sort_by
        if self.include_unapproved:
            persistent_params["is_approved"] = "false"
        persistent_params = urlencode(persistent_params)
        return persistent_params

    @property
    @memoized
    def results(self):
        start_at = (self.page - 1) * self.page_length
        sort_by_property = 'snapshot_time' if self.sort_by == 'newest' else 'full_downloads'
        return es_snapshot_query(self.params, SNAPSHOT_FACETS, start_at=start_at,
                                 size=self.page_length, sort_by=sort_by_property)

    @property
    def total_results(self):
        return self.results.get('hits', {}).get('total', 0)

    @property
    @memoized
    def selected_snapshots(self):
        hits = self.results.get('hits', {}).get('hits', [])
        hits = deduplicate(hits)
        domains = []
        for res in hits:
            try:
                domain = Domain.wrap(res['_source'])
                if domain.copied_from is not None:
                    # this avoids putting in snapshots in the list where the
                    # copied_from domain has been deleted.
                    domains.append(domain)
            except CopiedFromDeletedException as e:
                notify_exception(
                    self.request,
                    message=(
                        "Fetched Exchange Snapshot Error: {}. "
                        "The problem snapshot id: {}".format(
                            str(e), res['_source']['_id'])
                    )
                )

        return domains

    @property
    def page_context(self):
        return {
            'apps': self.selected_snapshots,
            'page': self.page,
            'prev_page': (self.page - 1),
            'next_page': (self.page + 1),
            'more_pages': False if self.total_results <= self.page * self.page_length else True,
            'sort_by': self.sort_by,
            'show_starter_apps': self.starter_apps,
            'include_unapproved': self.include_unapproved,
            'facet_map': fill_mapping_with_facets(SNAPSHOT_MAPPING, self.results, self.params),
            'facets': self.results.get("facets", []),
            'query_str': self.request.META['QUERY_STRING'],
            'search_query': self.params.get('search', [""])[0],
            'persistent_params': self.persistent_params,
        }


def es_snapshot_query(params, facets=None, terms=None, sort_by="snapshot_time", start_at=None, size=None):
    if terms is None:
        terms = ['is_approved', 'sort_by', 'search']
    if facets is None:
        facets = []
    q = {"sort": {sort_by: {"order": "desc"}},
         "query": {"bool": {"must": [
             {"match": {'doc_type': "Domain"}},
             {"term": {"published": True}},
             {"term": {"is_snapshot": True}},
             {"term": {"snapshot_head": True}}
         ]}},
         "filter": {"and": [{"term": {"is_approved": params.get('is_approved', None) or True}}]}}

    search_query = params.get('search', "")
    if search_query:
        q['query']['bool']['must'].append({
            "match": {
                "_all": {
                    "query": search_query,
                    "operator": "and"
                }
            }
        })

    return es_query(params, facets, terms, q, start_at=start_at, size=size)


@require_superuser
def approve_app(request, snapshot):
    domain_obj = Domain.get(snapshot)
    if request.GET.get('approve') == 'true':
        domain_obj.is_approved = True
        domain_obj.save()
    elif request.GET.get('approve') == 'false':
        domain_obj.is_approved = False
        domain_obj.save()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER') or reverse('appstore'))


def project_image(request, snapshot):
    project = Domain.get(snapshot)
    if project.image_path:
        image = project.fetch_attachment(project.image_path)
        return HttpResponse(image, content_type=project.image_type)
    else:
        raise Http404()


def project_documentation_file(request, snapshot):
    project = Domain.get(snapshot)
    if project.documentation_file_path:
        documentation_file = project.fetch_attachment(project.documentation_file_path)
        return HttpResponse(documentation_file, content_type=project.documentation_file_type)
    else:
        raise Http404()
