from datetime import datetime
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from corehq.apps.appstore.forms import AddReviewForm
from corehq.apps.appstore.models import Review
from corehq.apps.domain.decorators import require_superuser, login_and_domain_required
from corehq.apps.registration.forms import DomainRegistrationForm
from corehq.apps.reports.dispatcher import ReportDispatcher
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
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

PER_PAGE = 9

def appstore(request, template="appstore/appstore_base.html"):
    page = int(request.GET.get('page', 1))
    results = Domain.published_snapshots(include_unapproved=request.user.is_superuser, page=page, per_page=PER_PAGE)
    average_ratings = list()
    for result in results:
        average_ratings.append([result.name, Review.get_average_rating_by_app(result.original_doc)])
    more_pages = page * PER_PAGE < results.total_rows
    vals = dict(apps=results, average_ratings=average_ratings, page=page, prev_page=(page-1), next_page=(page+1), more_pages=more_pages)
    return render_to_response(request, template, vals)

def highest_rated(request, template="appstore/appstore_best.html"):
    page = int(request.GET.get('page', 1))
    results = Domain.published_snapshots(include_unapproved=request.user.is_superuser)
    #sort by popularity
    results = Domain.popular_sort(results, page)
    average_ratings = list()
    for result in results:
        average_ratings.append([result.name, Review.get_average_rating_by_app(result.original_doc)])
    more_pages = page * PER_PAGE < len(results)
    print(results)
    filter_by = 'best'
    vals = dict(apps=results, average_ratings=average_ratings, page=page, prev_page=(page-1), next_page=(page+1), more_pages=more_pages, filter_by=filter_by)
    return render_to_response(request, template, vals)

def project_info(request, domain, template="appstore/project_info.html"):
    dom = Domain.get_by_name(domain)
    if not dom or not dom.is_snapshot or not dom.published or (not dom.is_approved and not request.couch_user.is_domain_admin(domain)):
        raise Http404()

    if request.method == "POST":
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
                review = Review(title=title, rating=rating, user=user, info=info, date_published = date_published, domain=domain, original_doc=dom.original_doc)
            review.save()
        else:
            form = AddReviewForm()
    else:
        form = AddReviewForm()
        versioned = not request.GET.get('all', '')

    if versioned:
        reviews = Review.get_by_version(domain)
        average_rating = Review.get_average_rating_by_version(domain)
        num_ratings = Review.get_num_ratings_by_version(domain)
    else:
        reviews = Review.get_by_app(dom.original_doc)
        average_rating = Review.get_average_rating_by_app(dom.original_doc)
        num_ratings = Review.get_num_ratings_by_app(dom.original_doc)

    if average_rating:
        average_rating = round(average_rating, 1)

    all_link = ''
    if versioned:
        all_link = 'true'

    images = set()
    audio = set()
#    for app in dom.applications():
#        if app.doc_type == 'Application':
#            app = Application.get(app._id)
#            sorted_images, sorted_audio, has_error = utils.get_sorted_multimedia_refs(app)
#            images.update(i['url'] for i in app.get_template_map(sorted_images)[0] if i['url'])
#            audio.update(a['url'] for a in app.get_template_map(sorted_audio)[0] if a['url'])

    vals = dict(
        project=dom,
        form=form,
        reviews=reviews,
        average_rating=average_rating,
        num_ratings=num_ratings,
        versioned=versioned,
        all_link=all_link,
        images=images,
        audio=audio,
    )
    return render_to_response(request, template, vals)

def search_snapshots(request, filter_by = '', filter = '', template="appstore/appstore_base.html"):
    page = int(request.GET.get('page', 1))
    if filter_by != '':
        query = "%s:%s %s" % (filter_by, filter, request.GET['q'])
    else:
        query = request.GET['q']

    if query == '':
        return redirect('appstore')

    snapshots, total_rows = Domain.snapshot_search(query, page=page, per_page=PER_PAGE)
    more_pages = page * PER_PAGE < total_rows
    vals = dict(apps=snapshots, search_query=query, page=page, prev_page=(page-1), next_page=(page+1), more_pages=more_pages)
    return render_to_response(request, template, vals)

def filter_choices(request, filter_by, template="appstore/filter_choices.html"):
    if filter_by not in ('category', 'license', 'region', 'organization', 'author'):
        raise Http404("That page doesn't exist")

    if filter_by == 'category':
        choices = [(d.replace(' ', '+'), d) for d in Domain.field_by_prefix('project_type')]
    elif filter_by == 'organization':
        choices = [(o.name, o.title) for o in Organization.get_all()]
    elif filter_by == 'author':
        choices = [(d.replace(' ', '+'), d) for d in Domain.field_by_prefix('author')]
    elif filter_by == 'license':
        choices = LICENSES.items()
    elif filter_by == 'region':
        choices = [(d.replace(' ', '+'), d) for d in Domain.regions()]

    return render_to_response(request, template, {'choices': choices, 'filter_by': filter_by})

def filter_snapshots(request, filter_by, filter, template="appstore/appstore_base.html"):
    if filter_by not in ('category', 'license', 'region', 'organization', 'author'):
        raise Http404("That page doesn't exist")

    page = int(request.GET.get('page', 1))

    filter = filter.replace('+', ' ')

    query = '%s:"%s"' % (filter_by, filter)
    results, total_rows = Domain.snapshot_search(query, page=page, per_page=PER_PAGE)
    more_pages = page * PER_PAGE < total_rows
    vals = dict(apps=results, filter_by=filter_by, filter=filter, page=page, prev_page=(page-1), next_page=(page+1), more_pages=more_pages)
    return render_to_response(request, template, vals)

@datespan_default
def report_dispatcher(request, slug, return_json=False,
                      map='APPSTORE_INTERFACE_MAP', export=False, custom=False,
                      async=False, async_filters=False, static_only=False):

    def permissions_check(couch_user, domain, model):
        return True

    dummy = Domain.get_by_name('dumdum')

    if not dummy:
        dummy = Domain(name='dumdum',
            is_active=True,
            date_created=datetime.utcnow())
        dummy.save()

    mapping = getattr(settings, map, None)
    dispatcher = ReportDispatcher(mapping, permissions_check)
    return dispatcher.dispatch(request, dummy.name, slug, return_json, export,
                               custom, async, async_filters)

@require_superuser
def approve_app(request, domain):
    domain = Domain.get_by_name(domain)
    if request.GET.get('approve') == 'true':
        domain.is_approved = True
        domain.save()
    elif request.GET.get('approve') == 'false':
        domain.is_approved = False
        domain.save()
    return HttpResponseRedirect(reverse('appstore'))

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

@login_and_domain_required
def copy_snapshot(request, domain):
    dom = Domain.get_by_name(domain)
    if request.method == "POST" and dom.is_snapshot:
        args = {'domain_name': request.POST['new_project_name'], 'tos_confirmed': True}
        form = DomainRegistrationForm(args)

        print request.POST['new_project_name']
        print form.is_valid()
        print form.errors

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
