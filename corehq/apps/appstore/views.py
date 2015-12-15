import json
from urllib import urlencode
from corehq.apps.appstore.exceptions import CopiedFromDeletedException
from corehq.apps.registration.utils import create_30_day_trial
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.resource_conflict import retry_resource

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.template.loader import render_to_string
from django.shortcuts import render
from django.contrib import messages
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


def project_info(request, domain, template="appstore/project_info.html"):
    dom = Domain.get(domain)
    if not can_view_app(request, dom):
        raise Http404()
    copies = dom.copies_of_parent()
    images = set()
    audio = set()
    return render(request, template, {
        "project": dom,
        "applications": dom.full_applications(include_builds=False),
        "fixtures": FixtureDataType.by_domain(dom.name),
        "copies": copies,
        "images": images,
        "audio": audio,
        "url_base": reverse('appstore'),
        'display_import': True if getattr(request, "couch_user",
                                          "") and request.couch_user.get_domains() else False
    })


def deduplicate(hits):
    unique_names = set()
    unique_hits = []
    for hit in hits:
        if not hit['_source']['name'] in unique_names:
            unique_hits.append(hit)
            unique_names.add(hit['_source']['name'])
    return unique_hits


def appstore(request, template="appstore/appstore_base.html"):
    page_length = 10
    include_unapproved = True if request.GET.get('is_approved', "") == "false" else False
    if include_unapproved and not request.user.is_superuser:
        raise Http404()
    params, _ = parse_args_for_es(request)
    page = params.pop('page', 1)
    page = int(page[0] if isinstance(page, list) else page)
    results = es_snapshot_query(params, SNAPSHOT_FACETS)
    hits = results.get('hits', {}).get('hits', [])
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
                "Fetched Exchange Snapshot Error: {}. The problem snapshot id: {}".format(
                e.message, res['_source']['_id']
            ))

    starter_apps = request.GET.get('is_starter_app', None)
    sort_by = request.GET.get('sort_by', None)
    if sort_by == 'newest':
        pass
    else:
        d_results = Domain.hit_sort(d_results)

    persistent_params = {}
    if sort_by:
        persistent_params["sort_by"] = sort_by
    if include_unapproved:
        persistent_params["is_approved"] = "false"
    persistent_params = urlencode(persistent_params)  # json.dumps(persistent_params)

    more_pages = False if len(d_results) <= page * page_length else True

    facet_map = fill_mapping_with_facets(SNAPSHOT_MAPPING, results, params)
    vals = dict(
        apps=d_results[(page - 1) * page_length:page * page_length],
        page=page,
        prev_page=(page - 1),
        next_page=(page + 1),
        more_pages=more_pages,
        sort_by=sort_by,
        show_starter_apps=starter_apps,
        include_unapproved=include_unapproved,
        facet_map=facet_map,
        facets=results.get("facets", []),
        query_str=request.META['QUERY_STRING'],
        search_query=params.get('search', [""])[0],
        persistent_params=persistent_params,
    )
    return render(request, template, vals)


def appstore_api(request):
    params, facets = parse_args_for_es(request)
    results = es_snapshot_query(params, facets)
    return HttpResponse(json.dumps(results), content_type="application/json")


def es_snapshot_query(params, facets=None, terms=None, sort_by="snapshot_time"):
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

    return es_query(params, facets, terms, q)


@require_superuser
def approve_app(request, domain):
    domain = Domain.get(domain)
    if request.GET.get('approve') == 'true':
        domain.is_approved = True
        domain.save()
    elif request.GET.get('approve') == 'false':
        domain.is_approved = False
        domain.save()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER') or reverse('appstore'))


@login_required
@retry_resource(3)
def import_app(request, domain):
    user = request.couch_user
    if not user.is_eula_signed():
        messages.error(request, 'You must agree to our eula to download an app')
        return project_info(request, domain)

    from_project = Domain.get(domain)

    if request.method == 'POST' and from_project.is_snapshot:
        if not from_project.published:
            messages.error(request, "This project is not published and can't be downloaded")
            return project_info(request, domain)

        to_project_name = request.POST['project']
        if not user.is_member_of(to_project_name):
            messages.error(request, _("You don't belong to that project"))
            return project_info(request, domain)

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
        return HttpResponseRedirect(reverse('project_info', args=[domain]))


@login_required
def copy_snapshot(request, domain):
    user = request.couch_user
    if not user.is_eula_signed():
        messages.error(request, 'You must agree to our eula to download an app')
        return project_info(request, domain)

    dom = Domain.get(domain)
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
                return project_info(request, domain)

            if not form.is_valid():
                messages.error(request, form.errors)
                return project_info(request, domain)

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
                    return project_info(request, domain)

                # sign new project up for trial
                create_30_day_trial(new_domain)

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
            return project_info(request, domain)
    else:
        return HttpResponseRedirect(reverse('project_info', args=[domain]))


def project_image(request, domain):
    project = Domain.get(domain)
    if project.image_path:
        image = project.fetch_attachment(project.image_path)
        return HttpResponse(image, content_type=project.image_type)
    else:
        raise Http404()


def project_documentation_file(request, domain):
    project = Domain.get(domain)
    if project.documentation_file_path:
        documentation_file = project.fetch_attachment(project.documentation_file_path)
        return HttpResponse(documentation_file, content_type=project.documentation_file_type)
    else:
        raise Http404()


@login_required
def deployment_info(request, domain, template="appstore/deployment_info.html"):
    dom = Domain.get_by_name(domain)
    if not dom or not dom.deployment.public:
        raise Http404()

    # get facets
    results = es_deployments_query({}, DEPLOYMENT_FACETS)
    facet_map = fill_mapping_with_facets(DEPLOYMENT_MAPPING, results, {})

    return render(request, template, {
        'domain': dom,
        'search_url': reverse('deployments'),
        'url_base': reverse('deployments'),
        'facet_map': facet_map,
    })


@login_required
def deployments(request, template="appstore/deployments.html"):
    params, _ = parse_args_for_es(request)
    params = dict([(DEPLOYMENT_MAPPING.get(p, p), params[p]) for p in params])
    page = int(params.pop('page', 1))
    results = es_deployments_query(params, DEPLOYMENT_FACETS)
    d_results = [Domain.wrap(res['_source']) for res in results['hits']['hits']]

    more_pages = False if len(d_results) <= page * 10 else True

    facet_map = fill_mapping_with_facets(DEPLOYMENT_MAPPING, results, params)
    include_unapproved = True if request.GET.get('is_approved', "") == "false" else False
    vals = {'deployments': d_results[(page - 1) * 10:page * 10],
            'page': page,
            'prev_page': page - 1,
            'next_page': (page + 1),
            'more_pages': more_pages,
            'include_unapproved': include_unapproved,
            'facet_map': facet_map,
            'query_str': request.META['QUERY_STRING'],
            'search_url': reverse('deployments'),
            'search_query': params.get('search', [""])[0]}
    return render(request, template, vals)


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


def media_files(request, domain, template="appstore/media_files.html"):
    dom = Domain.get(domain)
    if not can_view_app(request, dom):
        raise Http404()

    return render(request, template, {
        "project": dom,
        "url_base": reverse('appstore')
    })
