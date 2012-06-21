import datetime
from django.core.urlresolvers import reverse
from django.http import Http404
from corehq.apps.appstore.forms import AddReviewForm, AppStoreAdvancedFilter
from corehq.apps.appstore.models import Review
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.registration.forms import DomainRegistrationForm
from dimagi.utils.web import render_to_response, json_response, get_url_base
from corehq.apps.orgs.models import Organization
from corehq.apps.domain.models import Domain, LICENSES
from dimagi.utils.couch.database import get_db
from django.contrib import messages

@require_superuser
def appstore(request, template="appstore/appstore_base.html"):
    apps = Domain.published_snapshots()[:40]
    if request.method == "POST":
        form = AppStoreAdvancedFilter(request.GET)
    else:
        form = AppStoreAdvancedFilter()
    vals = dict(apps=apps, form=form)
    return render_to_response(request, template, vals)

@require_superuser
def app_info(request, domain, template="appstore/app_info.html", versioned=None):
    dom = Domain.get_by_name(domain)
    if not dom or not dom.is_snapshot or not dom.published:
        raise Http404()
    if request.method == "POST":
        versioned = request.POST.get('versioned', '')
        nickname = request.POST.get('review_name', '')

        if nickname:
            form = AddReviewForm(request.POST)
#            pdb.set_trace()
            if form.is_valid():
                nickname = form.cleaned_data['review_name']
                title = form.cleaned_data['review_title']
                rating = form.cleaned_data['review_rating']
                info = form.cleaned_data['review_info']
                user = request.user.username
                date_published = datetime.datetime.now()
                review = Review(title=title, rating=rating, nickname=nickname, user=user, info=info, date_published = date_published, domain=domain, original_doc=dom.original_doc)
                review.save()
        else:
            form = AddReviewForm()
    else:
        form = AddReviewForm()

    if versioned:
        reviews = Review.get_by_version(domain)
        average_rating = Review.get_average_rating_by_version(domain)
        num_ratings = Review.get_num_ratings_by_version(domain)
    else:
        reviews = Review.get_by_app(dom.original_doc)
        average_rating = Review.get_average_rating_by_app(dom.original_doc)
        num_ratings = Review.get_num_ratings_by_app(dom.original_doc)
    average_rating = round(average_rating, 1)

    vals = dict(domain=dom,
        form=form,
        reviews=reviews,
        average_rating=average_rating,
        num_ratings=num_ratings,
        versioned=versioned
    )
    return render_to_response(request, template, vals)

@require_superuser
def search_snapshots(request, filter_by = '', filter = '', template="appstore/appstore_base.html"):
    if filter_by != '':
        query = "%s:%s %s" % (filter_by, filter, request.GET['q'])
    else:
        query = request.GET['q']

    snapshots = Domain.snapshot_search(query, limit=40)
    return render_to_response(request, template, {'apps': snapshots, 'search_query': query})

@require_superuser
def filter_choices(request, filter_by, template="appstore/filter_choices.html"):
    if filter_by not in ('category', 'license', 'region', 'organization'):
        raise Http404("That page doesn't exist")

    if filter_by == 'category':
        choices = [(d.replace(' ', '+'), d) for d in Domain.categories()]
    elif filter_by == 'organization':
        choices = [(o.name, o.title) for o in Organization.get_all()]
    elif filter_by == 'license':
        choices = LICENSES.items()
    elif filter_by == 'region':
        choices = [(d.replace(' ', '+'), d) for d in Domain.regions()]

    return render_to_response(request, template, {'choices': choices, 'filter_by': filter_by})

@require_superuser
def filter_snapshots(request, filter_by, filter, template="appstore/appstore_base.html"):
    if filter_by not in ('category', 'license', 'region', 'organization'):
        raise Http404("That page doesn't exist")

    filter = filter.replace('+', ' ')

    query = '%s:"%s"' % (filter_by, filter)
    results = get_db().search('domain/snapshot_search', q=query, limit=40)
    snapshots = map(Domain.get, [r['id'] for r in results])
    return render_to_response(request, template, {'apps': snapshots, 'filter_by': filter_by, 'filter': filter})
