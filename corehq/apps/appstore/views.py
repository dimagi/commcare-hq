import datetime
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from corehq.apps.appstore.forms import AddReviewForm
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
    vals = dict(apps=apps)
    return render_to_response(request, template, vals)

@require_superuser
def app_info(request, domain, template="appstore/app_info.html"):
    dom = Domain.get_by_name(domain)
    if request.method == "POST":
        form = AddReviewForm(request.POST)
        if form.is_valid():
            nickname = form.cleaned_data['review_name']
            title = form.cleaned_data['review_title']
            rating = form.cleaned_data['review_rating']
            info = form.cleaned_data['review_info']
            user = request.user.username
            date_published = datetime.datetime.now()
            review = Review(title=title, rating=rating, nickname=nickname, user=user, info=info, date_published = date_published, domain=domain)
            review.save()
    else:
        form = AddReviewForm()

    reviews = Review.get_by_app(domain)
    vals = dict(domain=dom, form=form, reviews=reviews)
    return render_to_response(request, template, vals)

@require_superuser
def search_snapshots(request, filter_by = '', filter = '', template="appstore/appstore_base.html"):
    if filter_by != '':
        query = "%s:%s %s" % (filter_by, filter, request.GET['q'])
    else:
        query = request.GET['q']
    results = get_db().search('domain/snapshot_search', q=query, limit=40)
    snapshots = map(Domain.get, [r['id'] for r in results])
    return render_to_response(request, template, {'apps': snapshots, 'search_query': query})

@require_superuser
def filter_choices(request, filter_by, template="appstore/filter_choices.html"):
    if filter_by not in ('category', 'license', 'region', 'organization'):
        return HttpResponseRedirect(reverse('appstore')) # does not exist

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
        return HttpResponseRedirect(reverse('appstore')) # does not exist

    filter = filter.replace('+', ' ')

    query = '%s:"%s"' % (filter_by, filter)
    results = get_db().search('domain/snapshot_search', q=query, limit=40)
    snapshots = map(Domain.get, [r['id'] for r in results])
    return render_to_response(request, template, {'apps': snapshots, 'filter_by': filter_by, 'filter': filter})
