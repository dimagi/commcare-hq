from datetime import datetime
import json
import logging
from urllib import urlencode
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse
from restkit.errors import RequestFailed
from corehq.apps.appstore.forms import AddReviewForm
from corehq.apps.appstore.models import Review
from corehq.apps.domain.decorators import require_previewer, login_and_domain_required
from corehq.apps.registration.forms import DomainRegistrationForm
from corehq.apps.users.models import Permissions
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import render_to_response, json_response, get_url_base
from corehq.apps.orgs.models import Organization
from corehq.apps.domain.models import Domain, LICENSES
from dimagi.utils.couch.database import get_db
from django.contrib import messages
from django.conf import settings
from corehq.apps.reports.views import datespan_default
from corehq.apps.hqmedia import utils
from corehq.apps.app_manager.models import Application
from django.shortcuts import redirect
import rawes

PER_PAGE = 9
SNAPSHOT_FACETS = ['project_type', 'license', 'region', 'author']
DEPLOYMENT_FACETS = ['deployment.region']
SNAPSHOT_MAPPING = {'category':'project_type', 'license': 'license', 'region': 'region', 'author': 'author'}
DEPLOYMENT_MAPPING = {'region': 'deployment.region'}


def rewrite_url(request, path):
    return HttpResponseRedirect('/exchange%s?%s' % (path, request.META['QUERY_STRING']))

def inverse_dict(d):
    return {v: k for k, v in d.iteritems()}

@require_previewer # remove for production
def project_info(request, domain, template="appstore/project_info.html"):
    dom = Domain.get_by_name(domain)
    if not dom or not dom.is_snapshot or (not dom.is_approved and not request.couch_user.is_domain_admin(domain)):
        raise Http404()

    if request.method == "POST" and dom.copied_from.name not in request.couch_user.get_domains():
        versioned = True
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
        versioned = request.GET.get('current', False)

    if versioned:
        reviews = Review.get_by_version(domain)
        average_rating = Review.get_average_rating_by_version(domain)
        num_ratings = Review.get_num_ratings_by_version(domain)
    else:
        reviews = Review.get_by_app(dom.copied_from._id)
        average_rating = Review.get_average_rating_by_app(dom.copied_from._id)
        num_ratings = Review.get_num_ratings_by_app(dom.copied_from._id)

    if average_rating:
        average_rating = round(average_rating, 1)

    current_link = ''
    if not versioned:
        current_link = 'true'

    images = set()
    audio = set()
#    for app in dom.applications():
#        if app.doc_type == 'Application':
#            app = Application.get(app._id)
#            sorted_images, sorted_audio, has_error = utils.get_sorted_multimedia_refs(app)
#            images.update(i['url'] for i in app.get_template_map(sorted_images)[0] if i['url'])
#            audio.update(a['url'] for a in app.get_template_map(sorted_audio)[0] if a['url'])

    # get facets
    results = es_snapshot_query({}, SNAPSHOT_FACETS)
    facets_sortables = generate_sortables_from_facets(results, {}, inverse_dict(SNAPSHOT_MAPPING))

    return render_to_response(request, template, {
        "project": dom,
        "form": form,
        "reviews": reviews,
        "average_rating": average_rating,
        "num_ratings": num_ratings,
        "versioned": versioned,
        "current_link": current_link,
        "images": images,
        "audio": audio,
        "sortables": facets_sortables,
        "url_base": reverse('appstore')
    })

def parse_args_for_es(request):
    """
    Parses a request's query string for url parameters. It specifically parses the facet url parameter so that each term
    is counted as a separate facet. e.g. 'facets=region author category' -> facets = ['region', 'author', 'category']
    """
    params = {}
    facets = []
    for attr in request.GET.iterlists():
        if attr[0] == 'facets':
            facets = attr[1][0].split()
            continue
        params[attr[0]] = attr[1][0] if len(attr[1]) < 2 else attr[1]
    return params, facets

def generate_sortables_from_facets(results, params=None, mapping={}):
    """
    Sortable is a list of tuples containing the field name (e.g. Category) and a list of dictionaries for each facet
    under that field (e.g. HIV and MCH are under Category). Each facet's dict contains the query string, display name,
    count and active-status for each facet.
    """
    params = {mapping.get(p, p): params[p] for p in params}
    def generate_query_string(attr, val):
        updated_params = params.copy()
        updated_params.update({attr: val})
        return "?%s" % urlencode(updated_params)

    def generate_facet_dict(f_name, ft):
        return {'url': generate_query_string(disp_facet, ft["term"]),
                'name': ft["term"] if not license else LICENSES.get(ft["term"]),
                'count': ft["count"],
                'active': params.get(disp_facet, "") == ft["term"]}

    sortable = []
    for facet in results.get("facets", []):
        license = (facet == 'license')
        disp_facet = mapping.get(facet, facet) # the user-facing name for this facet
        sortable.append((disp_facet, [generate_facet_dict(disp_facet, ft) for ft in results["facets"][facet]["terms"]]))

    return sortable

@require_previewer # remove for production
def appstore(request, template="appstore/appstore_base.html"):
    params, _ = parse_args_for_es(request)
    params = {SNAPSHOT_MAPPING.get(p, p): params[p] for p in params}
    page = int(params.pop('page', 1))
    results = es_snapshot_query(params, SNAPSHOT_FACETS)
    d_results = [Domain.wrap(res['_source']) for res in results['hits']['hits']]

    sort_by = request.GET.get('sort_by', None)
    if sort_by == 'best':
        d_results = Domain.popular_sort(d_results, page)
    elif sort_by == 'hits':
        d_results = Domain.hit_sort(d_results, page)

    average_ratings = list()
    for result in d_results:
        average_ratings.append([result.name, Review.get_average_rating_by_app(result.copied_from._id)])

    more_pages = False if len(d_results) <= page*10 else True

    facets_sortables = generate_sortables_from_facets(results, params, inverse_dict(SNAPSHOT_MAPPING))
    include_unapproved = True if request.GET.get('is_approved', "") == "false" else False
    vals = dict(apps=d_results[(page-1)*10:page*10],
        page=page,
        prev_page=(page-1),
        next_page=(page+1),
        more_pages=more_pages,
        sort_by=sort_by,
        average_ratings=average_ratings,
        include_unapproved=include_unapproved,
        sortables=facets_sortables,
        query_str=request.META['QUERY_STRING'])
    return render_to_response(request, template, vals)

@require_previewer # remove for production
def appstore_api(request):
    params, facets = parse_args_for_es(request)
    params = {SNAPSHOT_MAPPING.get(p, p): params[p] for p in params}
    results = es_snapshot_query(params, facets)
    return HttpResponse(json.dumps(results), mimetype="application/json")

def es_query(params, facets=[], terms=[], q={}):
    q["filter"] = q.get("filter", {})
    q["filter"]["and"] = q["filter"].get("and", [])
    for attr in params:
        if attr not in terms:
            attr_val = [params[attr].lower()] if isinstance(params[attr], basestring) else [p.lower() for p in params[attr]]
            q["filter"]["and"].append({"terms": {attr: attr_val}})

    def facet_filter(facet):
        ff = {"facet_filter": {}}
        ff["facet_filter"]["and"] = [clause for clause in q["filter"]["and"] if facet not in clause.get("terms", [])]
        return ff if ff["facet_filter"]["and"] else {}

    if facets:
        q["facets"] = {}
        for facet in facets:
            q["facets"][facet] = {"terms": {"field": facet}}
            q["facets"][facet].update(facet_filter(facet))

    if not q['filter']['and']:
        del q["filter"]

    es_url = "cc_exchange/domain/_search"
    es = rawes.Elastic('localhost:9200')
    ret_data = es.get(es_url, data=q)

    return ret_data

def es_snapshot_query(params, facets=[], terms=['is_approved', 'sort_by', 'search'], sort_by="snapshot_time"):
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

@require_previewer
def appstore_default(request):
    from corehq.apps.appstore.dispatcher import AppstoreDispatcher
    return HttpResponseRedirect(reverse(AppstoreDispatcher.name(), args=['advanced']))

@require_previewer # remove for production
def approve_app(request, domain):
    domain = Domain.get_by_name(domain)
    if request.GET.get('approve') == 'true':
        domain.is_approved = True
        domain.save()
    elif request.GET.get('approve') == 'false':
        domain.is_approved = False
        domain.save()
    meta = request.META
    return HttpResponseRedirect(request.META.get('HTTP_REFERER') or reverse('appstore'))

@require_previewer # remove for production
def copy_snapshot_app(request, domain):
    user = request.couch_user
    dom = Domain.get_by_name(domain)
    if request.method == 'POST':
        new_domain_name = request.POST['project']
        app_id = request.POST['app_id']
        if user.is_member_of(new_domain_name):
            doc_type = get_db().get(app_id)['doc_type']
            new_doc = dom.copy_component(doc_type, app_id, new_domain_name, user)

            messages.info(request, "Application successfully copied!")
            return HttpResponseRedirect(reverse('view_app', args=[new_domain_name, new_doc.id]))
    return HttpResponseRedirect(reverse('project_info', args=[domain]))

#@login_and_domain_required
@require_previewer # remove for production
def copy_snapshot(request, domain):
    dom = Domain.get_by_name(domain)
    if request.method == "POST" and dom.is_snapshot:
        args = {'domain_name': request.POST['new_project_name'], 'tos_confirmed': True}
        form = DomainRegistrationForm(args)

        if form.is_valid():
            new_domain = dom.save_copy(form.clean_domain_name(), user=request.couch_user)
        else:
            messages.error(request, form.errors)
            return project_info(request, domain)

        if new_domain is None:
            messages.error(request, "A project by that name already exists")
            return project_info(request, domain)

        messages.success(request, "Project copied successfully!")
        return redirect("domain_project_settings", new_domain.name)

@require_previewer # remove for production
def project_image(request, domain):
    project = Domain.get_by_name(domain)
    if project.image_path:
        image = project.fetch_attachment(project.image_path)
        return HttpResponse(image, content_type=project.image_type)
    else:
        raise Http404()

@require_previewer # remove for production
def deployment_info(request, domain, template="appstore/deployment_info.html"):
    dom = Domain.get_by_name(domain)
    if not dom or not dom.deployment.public:
        raise Http404()

    # get facets
    results = es_deployments_query({}, DEPLOYMENT_FACETS)
    facets_sortables = generate_sortables_from_facets(results, {}, inverse_dict(DEPLOYMENT_MAPPING))

    return render_to_response(request, template, {'domain': dom,
                                                  'search_url': reverse('deployments'),
                                                  'url_base': reverse('deployments'),
                                                  'sortables': facets_sortables})

@require_previewer # remove for production
def deployments(request, template="appstore/deployments.html"):
    params, _ = parse_args_for_es(request)
    params = {DEPLOYMENT_MAPPING.get(p, p): params[p] for p in params}
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
             'search_url': reverse('deployments')}
    return render_to_response(request, template, vals)

@require_previewer # remove for production
def deployments_api(request):
    params, facets = parse_args_for_es(request)
    params = {DEPLOYMENT_MAPPING.get(p, p): params[p] for p in params}
    results = es_deployments_query(params, facets)
    return HttpResponse(json.dumps(results), mimetype="application/json")

def es_deployments_query(params, facets=[], terms=['is_approved', 'sort_by', 'search'], sort_by="snapshot_time"):
    q = {"query":   {"bool": {"must":
                                  [{"match": {'doc_type': "Domain"}},
                                   {"term": {"deployment.public": True}}]}}}

    search_query = params.pop('search', "")
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