from datetime import datetime
import json
import logging
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

def rewrite_url(request, path):
    return HttpResponseRedirect('/exchange%s?%s' % (path, request.META['QUERY_STRING']))

def _appstore_context(context={}):
    context['sortables'] = [
            ('category', [(d.replace(' ', '+'), d, count) for d, count in Domain.field_by_prefix('project_type')]),
            ('region', [(d.replace(' ', '+'), d, count) for d, count in Domain.field_by_prefix('region')]),
            ('author', [(d.replace(' ', '+'), d, count) for d, count in Domain.field_by_prefix('author')]),
            ('license', [(d, LICENSES.get(d), count) for d, count in Domain.field_by_prefix('license')]),
        ]
    import pprint
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(context)
    return context

@require_previewer # remove for production
def appstore(request, template="appstore/appstore_base.html", sort_by=None):
    page = int(request.GET.get('page', 1))
    include_unapproved = (request.user.is_superuser and request.GET.get('unapproved', False))
    if not sort_by:
        results = Domain.published_snapshots(include_unapproved=include_unapproved, page=page, per_page=PER_PAGE)
        more_pages = page * PER_PAGE < results.total_rows and len(results) == PER_PAGE # hacky way to deal with approved vs unapproved
    else:
        total_results = Domain.published_snapshots(include_unapproved=include_unapproved)
        if sort_by == 'best':
            results = Domain.popular_sort(total_results, page)
            #more_pages = page * PER_PAGE < total_results and page <= 10
        elif sort_by == 'hits':
            results = Domain.hit_sort(total_results, page)
            #more_pages = page * PER_PAGE < len(total_results) and page <= 10
        more_pages = page * PER_PAGE < total_results.total_rows and len(results) == PER_PAGE # hacky way to deal with approved vs unapproved
    average_ratings = list()
    for result in results:
        average_ratings.append([result.name, Review.get_average_rating_by_app(result.copied_from._id)])

    return render_to_response(request, template, _appstore_context({
        'apps': results,
        'average_ratings': average_ratings,
        'page': page,
        'prev_page': (page-1),
        'next_page': (page+1),
        'more_pages': more_pages,
        'sort_by': sort_by,
        'include_unapproved': include_unapproved
    }))

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

    vals = _appstore_context(dict(
        project=dom,
        form=form,
        reviews=reviews,
        average_rating=average_rating,
        num_ratings=num_ratings,
        versioned=versioned,
        current_link=current_link,
        images=images,
        audio=audio,
    ))
    return render_to_response(request, template, vals)

@require_previewer # remove for production
def search_snapshots(request, filter_by='', filter='', template="appstore/appstore_base.html"):
    page = int(request.GET.get('page', 1))
    q = request.GET.get('q', '')
    if filter_by != '':
        query = "%s:%s %s" % (filter_by, filter, q)
    else:
        query = q

    if query == '':
        return redirect('appstore')

    try:
        snapshots, total_rows = Domain.snapshot_search(query, page=page, per_page=PER_PAGE)
    except RequestFailed:
        notify_exception(request, "Domain snapshot_search RequestFailed")
        messages.error(request, "Oops! Our search backend is experiencing problems. Please try again later.")
        return redirect('appstore')
    else:
        more_pages = page * PER_PAGE < total_rows
        vals = dict(apps=snapshots, search_query=query, page=page, prev_page=(page-1), next_page=(page+1), more_pages=more_pages)
        return render_to_response(request, template, _appstore_context(vals))

FILTERS = {'category': 'project_type', 'license': 'license', 'region': 'region', 'author': 'author'}

@require_previewer # remove for production
def filter_snapshots(request, filter_by, filter, template="appstore/appstore_base.html", sort_by=None):
    if filter_by not in ('category', 'license', 'region', 'author'): # 'organization',
        raise Http404("That page doesn't exist")

    page = int(request.GET.get('page', 1))
    filter = filter.replace('+', ' ')
    #query = '%s:"%s"' % (filter_by, filter)

#    results = Domain.get_by_field(FILTERS[filter_by], filter)
    results = es_snapshot_filter({FILTERS[filter_by]: filter})
    results = [Domain.wrap(res['_source']) for res in results['hits']['hits']]

    total_rows = len(results)

    if not sort_by:
        results = results[(page-1)*PER_PAGE : page*PER_PAGE]
    else:
        #results, total_rows = Domain.snapshot_search(query, per_page=None)
        if sort_by == 'best':
            results = Domain.popular_sort(results, page)
        elif sort_by == 'hits':
            results = Domain.hit_sort(results, page)

    more_pages = page * PER_PAGE < total_rows

    average_ratings = list()
    for result in results:
        average_ratings.append([result.name, Review.get_average_rating_by_app(result.copied_from._id)])

    vals = _appstore_context(dict(apps=results,
                                  filter_by=filter_by,
                                  filter=filter,
                                  filter_url=filter.replace(' ', '+'),
                                  page=page,
                                  prev_page=(page-1),
                                  next_page=(page+1),
                                  more_pages=more_pages,
                                  sort_by=sort_by,
                                  average_ratings=average_ratings))
    return render_to_response(request, template, vals)

def parse_args_for_filter(request):
    params = {}
    facets = []
    for attr in request.GET.iterlists():
        if attr[0] == 'facets':
            facets = attr[1][0].split()
            continue
        params[attr[0]] = attr[1][0] if len(attr[1]) < 2 else attr[1]
    return params, facets

def generate_sortables_from_facets(results, params=[]):
    param_strings = {}
    if params:
        for attr in params:
            val = params[attr]
            if not isinstance(val, basestring):
                val=" ".join(val)
            param_strings[attr] = "{}={}".format(attr, val)

    def generate_query_string(strings, attr, val):
        strs = strings.copy()
        strs[attr] = "{}={}".format(attr, val)
        return "?%s" % "&".join(strs.values())

    sortable = []
    for facet in results.get("facets", []):
        sortable.append((facet, [(generate_query_string(param_strings, facet, ft["term"]), ft["term"], ft["count"]) \
                                 for ft in results["facets"][facet]["terms"]]))
    return sortable or _appstore_context()

@require_previewer # remove for production
def snapshot_filter(request, template="appstore/appstore_base.html"):
    params, _ = parse_args_for_filter(request)
    page = int(params.pop('page', 1))
    facets = ['project_type', 'license', 'region', 'author']
    results = es_snapshot_filter(params, facets)
    d_results = [Domain.wrap(res['_source']) for res in results['hits']['hits']]

    sort_by = request.GET.get('sort_by', None)
    if sort_by == 'best':
        d_results = Domain.popular_sort(d_results, page)
    elif sort_by == 'hits':
        d_results = Domain.hit_sort(d_results, page)

    average_ratings = list()
    for result in d_results:
        average_ratings.append([result.name, Review.get_average_rating_by_app(result.copied_from._id)])

    more_pages = False if d_results <= page*10 else True

    facets_sortables = generate_sortables_from_facets(results, params)
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
def api_snapshot_filter(request):
    params, facets = parse_args_for_filter(request)
    results = es_snapshot_filter(params, facets)
    return HttpResponse(json.dumps(results), mimetype="application/json")

def es_snapshot_filter(params, facets=[], terms=['is_approved', 'sort_by'], sort_by="snapshot_time"):
    q = {"sort": {sort_by: {"order" : "desc"} },
         "query":   {"bool": {"must":
                                  [{"match": {'doc_type': "Domain"}},
                                   {"term": {"published": True}},
                                   {"term": {"is_snapshot": True}}]}},
         "filter":  {"and": [{"term": {"is_approved": params.get('is_approved', None) or True}}]}}

    for attr in params:
        if attr not in terms:
            attr_val = [params[attr].lower()] if isinstance(params[attr], basestring) else [p.lower() for p in params[attr]]
            q["filter"]["and"].append({"terms": {attr: attr_val}})

    def facet_filter(facet):
        ff = {"facet_filter": {}}
        ff["facet_filter"]["and"] = [clause for clause in q["filter"]["and"] if facet not in clause.get("terms", [])]
        return ff

    if facets:
        q["facets"] = {}
        for facet in facets:
            q["facets"][facet] = {"terms": {"field": facet}}
            q["facets"][facet].update(facet_filter(facet))

    es_url = "commcarehq/commcarehq/_search"
    es = rawes.Elastic('localhost:9200')
    ret_data = es.get(es_url, data=q)

    return ret_data

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