import datetime
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from corehq.apps.appstore.forms import AddReviewForm
from corehq.apps.appstore.models import Review
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.registration.forms import DomainRegistrationForm
from dimagi.utils.web import render_to_response, json_response, get_url_base
from corehq.apps.orgs.models import Organization
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.database import get_db
from django.contrib import messages

@require_superuser
def appstore(request, template="appstore/appstore_base.html"):
    apps = Domain.published_snapshots()
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
def search_snapshots(request, template="appstore/appstore_base.html"):
    query = 'type:snapshots %s' % request.GET['q']
    limit = None
    skip = 0
    snapshots = get_db().search('appstore/search', q=query, limit=limit, skip=skip, wrapper=Domain)
    return render_to_response(request, template, {'apps': snapshots})


