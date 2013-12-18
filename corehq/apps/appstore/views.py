from datetime import datetime
import json
from urllib import urlencode

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.template.loader import render_to_string
from django.shortcuts import render
from django.contrib import messages
from django.utils.translation import ugettext as _
from corehq.apps.app_manager.views import _clear_app_cache

from corehq.apps.appstore.forms import AddReviewForm
from corehq.apps.appstore.models import Review
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.users.models import CouchUser
from corehq.elastic import es_query, parse_args_for_es, generate_sortables_from_facets, fill_mapping_with_facets
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.database import apply_update


SNAPSHOT_FACETS = ['project_type', 'license', 'author.exact']
DEPLOYMENT_FACETS = ['deployment.region']
SNAPSHOT_MAPPING = [
    ("", True, [
        {"facet": "project_type", "name": "Category", "expanded": True },
        {
            "facet": "license",
            "name": "License",
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
        {"facet": "author.exact", "name": "Author", "expanded": True },
    ]),
]
DEPLOYMENT_MAPPING = [
    ("", True, [
        {"facet": "deployment.region", "name": "Region", "expanded": True },
    ]),
]




def rewrite_url(request, path):
    return HttpResponseRedirect('/exchange%s?%s' % (path, request.META['QUERY_STRING']))

def inverse_dict(d):
    return dict([(v, k) for k, v in d.iteritems()])

def can_view_app(req, dom):
    if not dom or not dom.is_snapshot:
        return False
    if not dom.is_approved and (not getattr(req, "couch_user", "") or not req.couch_user.is_domain_admin(dom.copied_from.name)):
        return False
    return True

def project_info(request, domain, template="appstore/project_info.html"):
    dom = Domain.get_by_name(domain)
    if not can_view_app(request, dom):
        raise Http404()

    if request.method == "POST" and dom.copied_from.name not in request.couch_user.get_domains():
        form = AddReviewForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['review_title']
            rating = int(request.POST.get('rating'))
            if rating < 1:
                rating = 1
            if rating > 5:
                rating = 5
            info = form.cleaned_data['review_info']
            date_published = datetime.now()
            user = request.user.username

            old_review = Review.get_by_version_and_user(domain, user)

            if len(old_review) > 0: # replace old review
                review = old_review[0]
                review.title = title
                review.rating = rating
                review.info = info
                review.date_published = date_published
            else:
                review = Review(title=title, rating=rating, user=user, info=info, date_published = date_published, domain=domain, project_id=dom.copied_from._id)
            review.save()
        else:
            form = AddReviewForm()
    else:
        form = AddReviewForm()

    copies = dom.copies_of_parent()

    reviews = Review.get_by_app(dom.copied_from._id)
    average_rating = Review.get_average_rating_by_app(dom.copied_from._id)
    num_ratings = Review.get_num_ratings_by_app(dom.copied_from._id)

    if average_rating:
        average_rating = round(average_rating, 1)

    images = set()
    audio = set()

    return render(request, template, {
        "project": dom,
        "applications": dom.full_applications(include_builds=False),
        "form": form,
        "copies": copies,
        "reviews": reviews,
        "average_rating": average_rating,
        "num_ratings": num_ratings,
        "images": images,
        "audio": audio,
        "url_base": reverse('appstore'),
        'display_import': True if getattr(request, "couch_user", "") and request.couch_user.get_domains() else False
    })

def appstore(request, template="appstore/appstore_base.html"):
    page_length = 10
    include_unapproved = True if request.GET.get('is_approved', "") == "false" else False
    if include_unapproved and not request.user.is_superuser:
        raise Http404()
    params, _ = parse_args_for_es(request)
    page = params.pop('page', 1)
    page = int(page[0] if isinstance(page, list) else page)
    results = es_snapshot_query(params, SNAPSHOT_FACETS)
    d_results = [Domain.wrap(res['_source']) for res in results.get('hits', {}).get('hits', [])]

    sort_by = request.GET.get('sort_by', None)
    if sort_by == 'best':
        d_results = Domain.popular_sort(d_results)
    elif sort_by == 'newest':
        pass
    else:
        d_results = Domain.hit_sort(d_results)

    persistent_params = {}
    if sort_by:
        persistent_params["sort_by"] = sort_by
    if include_unapproved:
        persistent_params["is_approved"] = "false"
    persistent_params = urlencode(persistent_params) # json.dumps(persistent_params)

    average_ratings = list()
    for result in d_results:
        average_ratings.append([result.name, Review.get_average_rating_by_app(result.copied_from._id)])

    more_pages = False if len(d_results) <= page*page_length else True

    facet_map = fill_mapping_with_facets(SNAPSHOT_MAPPING, results, params)
    vals = dict(
        apps=d_results[(page-1)*page_length:page*page_length],
        page=page,
        prev_page=(page-1),
        next_page=(page+1),
        more_pages=more_pages,
        sort_by=sort_by,
        average_ratings=average_ratings,
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
    return HttpResponse(json.dumps(results), mimetype="application/json")

def es_snapshot_query(params, facets=None, terms=None, sort_by="snapshot_time"):
    if terms is None:
        terms = ['is_approved', 'sort_by', 'search']
    if facets is None:
        facets = []
    q = {"sort": {sort_by: {"order" : "desc"} },
         "query":   {"bool": {"must":
                                  [{"match": {'doc_type': "Domain"}},
                                   {"term": {"published": True}},
                                   {"term": {"is_snapshot": True}}]}},
         "filter":  {"and": [{"term": {"is_approved": params.get('is_approved', None) or True}}]}}

    search_query = params.get('search', "")
    if search_query:
        q['query']['bool']['must'].append({
            "match" : {
                "_all" : {
                    "query" : search_query,
                    "operator" : "and"
                }
            }
        })

    return es_query(params, facets, terms, q)

def appstore_default(request):
    from corehq.apps.appstore.dispatcher import AppstoreDispatcher
    return HttpResponseRedirect(reverse(AppstoreDispatcher.name(), args=['advanced']))

@require_superuser
def approve_app(request, domain):
    domain = Domain.get_by_name(domain)
    if request.GET.get('approve') == 'true':
        domain.is_approved = True
        domain.save()
    elif request.GET.get('approve') == 'false':
        domain.is_approved = False
        domain.save()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER') or reverse('appstore'))

@login_required
def import_app(request, domain):
    user = request.couch_user
    if not user.is_eula_signed():
        messages.error(request, 'You must agree to our eula to download an app')
        return project_info(request, domain)

    from_project = Domain.get_by_name(domain)

    if request.method == 'POST' and from_project.is_snapshot:
        if not from_project.published:
            messages.error(request, "This project is not published and can't be downloaded")
            return project_info(request, domain)

        to_project_name = request.POST['project']
        if not user.is_member_of(to_project_name):
            messages.error(request, _("You don't belong to that project"))
            return project_info(request, domain)

        for app in from_project.full_applications(include_builds=False):
            new_doc = from_project.copy_component(app['doc_type'], app.get_id, to_project_name, user)
        _clear_app_cache(request, to_project_name)

        from_project.downloads += 1
        from_project.save()
        messages.success(request, render_to_string("appstore/partials/view_wiki.html", {"pre": _("Application successfully imported!")}), extra_tags="html")
        return HttpResponseRedirect(reverse('view_app', args=[to_project_name, new_doc.id]))
    else:
        return HttpResponseRedirect(reverse('project_info', args=[domain]))

@login_required
def copy_snapshot(request, domain):
    user = request.couch_user
    if not user.is_eula_signed():
        messages.error(request, 'You must agree to our eula to download an app')
        return project_info(request, domain)

    dom = Domain.get_by_name(domain)
    if request.method == "POST" and dom.is_snapshot:
        from corehq.apps.registration.forms import DomainRegistrationForm
        args = {'domain_name': request.POST['new_project_name'], 'eula_confirmed': True}
        form = DomainRegistrationForm(args)

        if request.POST.get('new_project_name', ""):
            if not dom.published:
                messages.error(request, "This project is not published and can't be downloaded")
                return project_info(request, domain)

            if form.is_valid():
                new_domain = dom.save_copy(form.clean_domain_name(), user=user)
            else:
                messages.error(request, form.errors)
                return project_info(request, domain)

            if new_domain is None:
                messages.error(request, _("A project by that name already exists"))
                return project_info(request, domain)

            def inc_downloads(d):
                d.downloads += 1

            apply_update(dom, inc_downloads)
            messages.success(request, render_to_string("appstore/partials/view_wiki.html", {"pre": _("Project copied successfully!")}), extra_tags="html")
            return HttpResponseRedirect(reverse('view_app',
                args=[new_domain.name, new_domain.full_applications()[0].get_id]))
        else:
            messages.error(request, _("You must specify a name for the new project"))
            return project_info(request, domain)
    else:
        return HttpResponseRedirect(reverse('project_info', args=[domain]))

def project_image(request, domain):
    project = Domain.get_by_name(domain)
    if project.image_path:
        image = project.fetch_attachment(project.image_path)
        return HttpResponse(image, content_type=project.image_type)
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

    more_pages = False if len(d_results) <= page*10 else True

    facets_sortables = generate_sortables_from_facets(results, params, inverse_dict(DEPLOYMENT_MAPPING))
    include_unapproved = True if request.GET.get('is_approved', "") == "false" else False
    vals = { 'deployments': d_results[(page-1)*10:page*10],
             'page': page,
             'prev_page': page-1,
             'next_page': (page+1),
             'more_pages': more_pages,
             'include_unapproved': include_unapproved,
             'sortables': facets_sortables,
             'query_str': request.META['QUERY_STRING'],
             'search_url': reverse('deployments'),
             'search_query': params.get('search', [""])[0]}
    return render(request, template, vals)

def deployments_api(request):
    params, facets = parse_args_for_es(request)
    params = dict([(DEPLOYMENT_MAPPING.get(p, p), params[p]) for p in params])
    results = es_deployments_query(params, facets)
    return HttpResponse(json.dumps(results), mimetype="application/json")

def es_deployments_query(params, facets=None, terms=None, sort_by="snapshot_time"):
    if terms is None:
        terms = ['is_approved', 'sort_by', 'search']
    if facets is None:
        facets = []
    q = {"query":   {"bool": {"must":
                                  [{"match": {'doc_type': "Domain"}},
                                   {"term": {"deployment.public": True}}]}}}

    search_query = params.get('search', "")
    if search_query:
        q['query']['bool']['must'].append({
            "match" : {
                "_all" : {
                    "query" : search_query,
                    "operator" : "and"
                }
            }
        })
    return es_query(params, facets, terms, q)

def media_files(request, domain, template="appstore/media_files.html"):
    dom = Domain.get_by_name(domain)
    if not can_view_app(request, dom):
        raise Http404()

    return render(request, template, {
        "project": dom,
        "url_base": reverse('appstore')
    })
