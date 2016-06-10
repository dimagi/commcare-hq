import json
from urllib import urlencode
from django.utils.decorators import method_decorator
from corehq.apps.appstore.exceptions import CopiedFromDeletedException
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.style.decorators import use_bootstrap3
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.resource_conflict import retry_resource

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.template.loader import render_to_string
from django.contrib import messages
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception
from dimagi.utils.name_to_url import name_to_url
from django.utils.translation import ugettext as _, ugettext_lazy
from corehq.apps.app_manager.views.apps import clear_app_cache

from corehq.apps.domain.decorators import require_superuser
from corehq.apps.domain.exceptions import NameUnavailableException
from corehq.elastic import es_query, parse_args_for_es, fill_mapping_with_facets
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.database import apply_update
from corehq.apps.fixtures.models import FixtureDataType


SNAPSHOT_FACETS = ['project_type', 'license', 'author.exact', 'is_starter_app']
DEPLOYMENT_FACETS = ['deployment.region']
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
DEPLOYMENT_MAPPING = [
    ("", True, [
        {"facet": "deployment.region", "name": "Region", "expanded": True},
    ]),
]


def rewrite_url(request, path):
    return HttpResponseRedirect('/exchange%s?%s' % (path, request.META['QUERY_STRING']))


def inverse_dict(d):
    return dict([(v, k) for k, v in d.iteritems()])


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

    @use_bootstrap3
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if self.include_unapproved and not self.request.user.is_superuser:
            raise Http404()
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
        return es_snapshot_query(self.params, SNAPSHOT_FACETS, start_at=start_at, size=self.page_length)

    @property
    def total_results(self):
        return self.results.get('hits', {}).get('total', 0)

    @property
    @memoized
    def d_results(self):
        hits = self.results.get('hits', {}).get('hits', [])
        hits = deduplicate(hits)
        d_results = []
        for res in hits:
            try:
                domain = Domain.wrap(res['_source'])
                if domain.copied_from is not None:
                    # this avoids putting in snapshots in the list where the
                    # copied_from domain has been deleted.
                    d_results.append(domain)
            except CopiedFromDeletedException as e:
                notify_exception(
                    self.request,
                    message=(
                        "Fetched Exchange Snapshot Error: {}. "
                        "The problem snapshot id: {}".format(
                            e.message, res['_source']['_id'])
                    )
                )
        if self.sort_by == 'newest':
            pass
        else:
            d_results = Domain.hit_sort(d_results)
        return d_results

    @property
    def page_context(self):
        return {
            'apps': self.d_results,
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


class ProjectInformationView(BaseCommCareExchangeSectionView):
    urlname = 'project_info'
    template_name = 'appstore/project_info.html'
    page_title = _("Project Information")

    @property
    def snapshot(self):
        return self.kwargs['snapshot']

    @property
    @memoized
    def project(self):
        return Domain.get(self.snapshot)

    def dispatch(self, request, *args, **kwargs):
        if not can_view_app(request, self.project):
            raise Http404()
        return super(ProjectInformationView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.snapshot,))

    @property
    def page_context(self):
        return {
            'project': self.project,
            'applications': self.project.full_applications(include_builds=False),
            'fixtures': FixtureDataType.by_domain(self.project.name),
            'copies': self.project.copies_of_parent(),
            'images': set(),
            'audio': set(),
            'url_base': reverse(CommCareExchangeHomeView.urlname),
            'display_import': getattr(
                self.request, 'couch_user', ''
            ) and self.request.couch_user.get_domains(),
        }


def appstore_api(request):
    params, facets = parse_args_for_es(request)
    results = es_snapshot_query(params, facets)
    return HttpResponse(json.dumps(results), content_type="application/json")


def es_snapshot_query(params, facets=None, terms=None, sort_by="snapshot_time", start_at=None, size=None):
    if terms is None:
        terms = ['is_approved', 'sort_by', 'search']
    if facets is None:
        facets = []
    q = {"sort": {sort_by: {"order": "desc"}},
         "query": {"bool": {"must": [
             {"match": {'doc_type': "Domain"}},
             {"term": {"published": True}},
             {"term": {"is_snapshot": True}}
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
    domain = Domain.get(snapshot)
    if request.GET.get('approve') == 'true':
        domain.is_approved = True
        domain.save()
    elif request.GET.get('approve') == 'false':
        domain.is_approved = False
        domain.save()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER') or reverse('appstore'))


@login_required
@retry_resource(3)
def import_app(request, snapshot):
    user = request.couch_user
    if not user.is_eula_signed():
        messages.error(request, 'You must agree to our eula to download an app')
        return HttpResponseRedirect(reverse(ProjectInformationView.urlname, args=[snapshot]))

    from_project = Domain.get(snapshot)

    if request.method == 'POST' and from_project.is_snapshot:
        if not from_project.published:
            messages.error(request, "This project is not published and can't be downloaded")
            return HttpResponseRedirect(reverse(ProjectInformationView.urlname, args=[snapshot]))

        to_project_name = request.POST['project']
        if not user.is_member_of(to_project_name):
            messages.error(request, _("You don't belong to that project"))
            return HttpResponseRedirect(reverse(ProjectInformationView.urlname, args=[snapshot]))

        full_apps = from_project.full_applications(include_builds=False)
        assert full_apps, 'Bad attempt to copy apps from a project without any!'
        for app in full_apps:
            new_doc = from_project.copy_component(app['doc_type'], app.get_id, to_project_name, user)
        clear_app_cache(request, to_project_name)

        from_project.downloads += 1
        from_project.save()
        messages.success(request, render_to_string("appstore/partials/view_wiki.html",
                                                   {"pre": _("Application successfully imported!")}),
                         extra_tags="html")
        return HttpResponseRedirect(reverse('view_app', args=[to_project_name, new_doc.id]))
    else:
        return HttpResponseRedirect(reverse(ProjectInformationView.urlname, args=[snapshot]))


@login_required
def copy_snapshot(request, snapshot):
    user = request.couch_user
    if not user.is_eula_signed():
        messages.error(request, 'You must agree to our eula to download an app')
        return HttpResponseRedirect(reverse(ProjectInformationView.urlname, args=[snapshot]))

    dom = Domain.get(snapshot)
    if request.method == "POST" and dom.is_snapshot:
        assert dom.full_applications(include_builds=False), 'Bad attempt to copy project without any apps!'

        from corehq.apps.registration.forms import DomainRegistrationForm

        args = {
            'domain_name': request.POST['new_project_name'],
            'hr_name': request.POST['new_project_name'],
            'eula_confirmed': True,
        }
        form = DomainRegistrationForm(args)

        if request.POST.get('new_project_name', ""):
            if not dom.published:
                messages.error(request, _("This project is not published and can't be downloaded"))
                return HttpResponseRedirect(reverse(ProjectInformationView.urlname, args=[snapshot]))

            if not form.is_valid():
                messages.error(request, form.errors)
                return HttpResponseRedirect(reverse(ProjectInformationView.urlname, args=[snapshot]))

            new_domain_name = name_to_url(form.cleaned_data['hr_name'], "project")
            with CriticalSection(['copy_domain_snapshot_{}_to_{}'.format(dom.name, new_domain_name)]):
                try:
                    new_domain = dom.save_copy(new_domain_name,
                                               new_hr_name=form.cleaned_data['hr_name'],
                                               user=user)
                    if new_domain.commtrack_enabled:
                        new_domain.convert_to_commtrack()

                except NameUnavailableException:
                    messages.error(request, _("A project by that name already exists"))
                    return HttpResponseRedirect(reverse(ProjectInformationView.urlname, args=[snapshot]))

            def inc_downloads(d):
                d.downloads += 1

            apply_update(dom, inc_downloads)
            messages.success(request, render_to_string("appstore/partials/view_wiki.html",
                                                       {"pre": _("Project copied successfully!")}),
                             extra_tags="html")
            return HttpResponseRedirect(reverse('view_app',
                                                args=[new_domain.name, new_domain.full_applications()[0].get_id]))
        else:
            messages.error(request, _("You must specify a name for the new project"))
            return HttpResponseRedirect(reverse(ProjectInformationView.urlname, args=[snapshot]))
    else:
        return HttpResponseRedirect(reverse(ProjectInformationView.urlname, args=[snapshot]))


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


class DeploymentInfoView(BaseCommCareExchangeSectionView):
    urlname = 'deployment_info'
    template_name = 'appstore/deployment_info.html'

    @property
    def snapshot(self):
        return self.kwargs['snapshot']

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.snapshot))

    @property
    def project(self):
        return Domain.get_by_name(self.snapshot)

    def dispatch(self, request, *args, **kwargs):
        if not self.project or not self.project.deployment.public:
            raise Http404()
        return super(DeploymentInfoView, self).dispatch(request, *args, **kwargs)

    def page_context(self):
        results = es_deployments_query({}, DEPLOYMENT_FACETS)
        facet_map = fill_mapping_with_facets(DEPLOYMENT_MAPPING, results, {})
        return {
            'domain': self.project,
            'search_url': reverse(DeploymentsView.urlname),
            'url_base': reverse(DeploymentsView.urlname),
            'facet_map': facet_map,
        }


class DeploymentsView(BaseCommCareExchangeSectionView):
    urlname = 'deployments'
    template_name = 'appstore/deployments.html'
    projects_per_page = 10

    @property
    @memoized
    def params(self):
        params, _ = parse_args_for_es(self.request)
        params = dict([(DEPLOYMENT_MAPPING.get(p, p), params[p]) for p in params])
        return params

    @property
    def page(self):
        return int(self.params.pop('page', 1))

    @property
    @memoized
    def results(self):
        return es_deployments_query(self.params, DEPLOYMENT_FACETS)

    @property
    @memoized
    def d_results(self):
        d_results = [Domain.wrap(res['_source']) for res in self.results['hits']['hits']]
        return d_results

    @property
    def page_context(self):
        more_pages = False if len(self.d_results) <= self.page * self.projects_per_page else True
        facet_map = fill_mapping_with_facets(DEPLOYMENT_MAPPING, self.results, self.params)
        include_unapproved = True if self.request.GET.get('is_approved', "") == "false" else False
        deployments = self.d_results[(self.page - 1) * self.projects_per_page:self.page * self.projects_per_page]
        return {
            'deployments': deployments,
            'page': self.page,
            'prev_page': self.page - 1,
            'next_page': (self.page + 1),
            'more_pages': more_pages,
            'include_unapproved': include_unapproved,
            'facet_map': facet_map,
            'query_str': self.request.META['QUERY_STRING'],
            'search_url': reverse(self.urlname),
            'search_query': self.params.get('search', [""])[0]
        }


def deployments_api(request):
    params, facets = parse_args_for_es(request)
    params = dict([(DEPLOYMENT_MAPPING.get(p, p), params[p]) for p in params])
    results = es_deployments_query(params, facets)
    return HttpResponse(json.dumps(results), content_type="application/json")


def es_deployments_query(params, facets=None, terms=None, sort_by="snapshot_time"):
    if terms is None:
        terms = ['is_approved', 'sort_by', 'search']
    if facets is None:
        facets = []
    q = {"query": {"bool": {"must": [{"match": {'doc_type': "Domain"}},
                                     {"term": {"deployment.public": True}}]}}}

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
    return es_query(params, facets, terms, q)


class MediaFilesView(BaseCommCareExchangeSectionView):
    urlname = 'media_files'
    template_name = 'appstore/media_files.html'

    def dispatch(self, request, *args, **kwargs):
        if not can_view_app(request, self.project):
            raise Http404()
        return super(MediaFilesView, self).dispatch(request, *args, **kwargs)

    @property
    def snapshot(self):
        return self.kwargs['snapshot']

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.snapshot,))

    @property
    @memoized
    def project(self):
        return Domain.get(self.snapshot)

    @property
    def page_context(self):
        return {
            "project": self.project,
            "url_base": reverse(CommCareExchangeHomeView.urlname)
        }
