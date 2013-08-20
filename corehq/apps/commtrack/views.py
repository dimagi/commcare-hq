from collections import defaultdict
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
from django.shortcuts import render

from corehq.apps.domain.decorators import require_superuser, domain_admin_required, require_previewer, login_and_domain_required
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.management.commands import bootstrap_psi
from corehq.apps.commtrack.models import Product
from corehq.apps.commtrack.forms import ProductForm
from corehq.apps.locations.models import Location
from soil.util import expose_download
import uuid
from django.core.urlresolvers import reverse
from django.contrib import messages
from corehq.apps.commtrack.tasks import import_locations_async,\
    import_stock_reports_async
import json
from couchdbkit import ResourceNotFound
import csv
from dimagi.utils.couch.database import iter_docs
import itertools

DEFAULT_PRODUCT_LIST_LIMIT = 10

@domain_admin_required # TODO: will probably want less restrictive permission
def product_list(request, domain, template="commtrack/manage/products.html"):
    page = request.GET.get('page', 1)
    limit = request.GET.get('limit', DEFAULT_PRODUCT_LIST_LIMIT)

    show_inactive = json.loads(request.GET.get('show_inactive', 'false'))

    total = len(Product.by_domain(domain))

    context = {
        'domain': domain,
    }
    context.update(
        product_list=dict(
            page=page,
            limit=limit,
            total=total,
        ),
        show_inactive=show_inactive,
        pagination_limit_options=range(DEFAULT_PRODUCT_LIST_LIMIT, 51, DEFAULT_PRODUCT_LIST_LIMIT)
    )
    return render(request, template, context)

@domain_admin_required # TODO: will probably want less restrictive permission
def product_fetch(request, domain):
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', DEFAULT_PRODUCT_LIST_LIMIT))
    skip = (page-1)*limit

    sort_by = request.GET.get('sortBy', 'abc')

    show_inactive = json.loads(request.GET.get('show_inactive', 'false'))

    products = Product.by_domain(domain) #limit=limit, skip=skip)
    def product_data(p):
        info = p._doc
        info['edit_url'] = reverse('commtrack_product_edit', kwargs={'domain': domain, 'prod_id': p._id})
        return info

    return HttpResponse(json.dumps(dict(
        success=True,
        current_page=page,
        product_list=[product_data(p) for p in products],
    )), 'text/json')

@domain_admin_required # TODO: will probably want less restrictive permission
def product_edit(request, domain, prod_id=None): 
    if prod_id:
        try:
            product = Product.get(prod_id)
        except ResourceNotFound:
            raise Http404
    else:
        product = Product(domain=domain)

    if request.method == "POST":
        form = ProductForm(product, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product saved!')
            return HttpResponseRedirect(reverse('commtrack_product_list', kwargs={'domain': domain}))
    else:
        form = ProductForm(product)

    context = {
        'domain': domain,
        'product': product,
        'form': form,
    }

    template="commtrack/manage/product.html"
    return render(request, template, context)

@require_superuser
def bootstrap(request, domain):
    if request.method == "POST":
        D = Domain.get_by_name(domain)

        if D.commtrack_enabled:
            return HttpResponse('already configured', 'text/plain')
        else:
            bootstrap_psi.one_time_setup(D)
            return HttpResponse('set up successfully', 'text/plain')

    return render(request, 'commtrack/debug/bootstrap.html', {
        'domain': domain,
        }
    )

@require_superuser
def location_import(request, domain):
    if request.method == "POST":
        upload = request.FILES.get('locs')
        if not upload:
            return HttpResponse('no file uploaded')
        update_existing = bool(request.POST.get('update'))

        # stash this in soil to make it easier to pass to celery
        file_ref = expose_download(upload.read(),
                                   expiry=1*60*60)
        download_id = uuid.uuid4().hex
        import_locations_async.delay(download_id, domain, file_ref.download_id, update_existing)
        return _async_in_progress(request, domain, download_id)

    return HttpResponse("""
<form method="post" action="" enctype="multipart/form-data">
  <div><input type="file" name="locs" /></div>
  <div><input id="update" type="checkbox" name="update" /> <label for="update">Update existing?</label></div>
  <div><button type="submit">Import locations</button></div>
</form>
""")

@require_superuser
def historical_import(request, domain):
    if request.method == "POST":
        file_ref = expose_download(request.FILES['history'].read(),
                                   expiry=1*60*60)
        download_id = uuid.uuid4().hex
        import_stock_reports_async.delay(download_id, domain, file_ref.download_id)
        return _async_in_progress(request, domain, download_id)

    return HttpResponse("""
<form method="post" action="" enctype="multipart/form-data">
  <div><input type="file" name="history" /></div>
  <div><button type="submit">Import historical stock reports</button></div>
</form>
""")

def _async_in_progress(request, domain, download_id):
    messages.success(request,
        'Your upload is in progress. You can check the progress <a href="%s">here</a>.' %\
        (reverse('hq_soil_download', kwargs={'domain': domain, 'download_id': download_id})),
        extra_tags="html")
    return HttpResponseRedirect(reverse('domain_homepage', args=[domain]))


@require_previewer
def charts(request, domain, template="commtrack/charts.html"):
    products = Product.by_domain(domain)
    prod_codes = [p.code for p in products]
    prod_codes.extend(range(20))

    from random import randint
    num_facilities = randint(44, 444)


    ### gen fake data
    def vals():
        tot = 0
        l = []
        for i in range(4):
            v = randint(0, num_facilities - tot)
            l.append(v)
            tot += v
        l.append(num_facilities - tot)
        return l

    statuses = [
        {"key": "stocked out", "color": "#e00707"},
        {"key": "under stock", "color": "#ffb100"},
        {"key": "adequate stock", "color": "#4ac925"},
        {"key": "overstocked", "color": "#b536da"},
        {"key": "unknown", "color": "#ABABAB"}
    ]

    for s in statuses:
        s["values"] = []

    for i, p in enumerate(prod_codes):
        vs = vals()
        for j in range(5):
            statuses[j]["values"].append({"x": p, "y": vs[j]})

    # colors don't actually work correctly for pie charts
    resp_values = [
        {"label": "Submitted on Time", "color": "#4ac925", "value": randint(0, 40)},
        {"label": "Didn't respond", "color": "#ABABAB", "value": randint(0, 20)},
        {"label": "Submitted Late", "color": "#e00707", "value": randint(0, 8)},
    ]
    response_data = [{
        "key": "Current Late Report",
        "values": resp_values
    }]

    ctxt = {
        "domain": domain,
        "stock_data": statuses,
        "response_data": response_data,
    }
    return render(request, template, ctxt)

@require_superuser
def location_dump(request, domain):
    loc_ids = [row['id'] for row in Location.view('commtrack/locations_by_code', startkey=[domain], endkey=[domain, {}])]
    
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="locations_%s.csv"' % domain

    w = csv.writer(resp)
    w.writerow(['UUID', 'Location Type', 'SMS Code'])
    for raw in iter_docs(Location.get_db(), loc_ids):
        loc = Location.wrap(raw)
        w.writerow([loc._id, loc.location_type, loc.site_code])
    return resp

@login_and_domain_required
def api_query_supply_point(request, domain):
    id = request.GET.get('id')
    query = request.GET.get('name', '')
    
    def loc_to_payload(loc):
        return {'id': loc._id, 'name': loc.name}

    if id:
        try:
            loc = Location.get(id)
            return HttpResponse(json.dumps(loc_to_payload(loc)), 'text/json')

        except ResourceNotFound:
            return HttpResponseNotFound(json.dumps({'message': 'no location with is %s found' % id}, 'text/json'))

    else:
        LIMIT = 100
        loc_types = [loc_type.name for loc_type in Domain.get_by_name(domain).commtrack_settings.location_types if not loc_type.administrative]

        def get_locs(type):
            # TODO use ES instead?
            q = query.lower()
            startkey = [domain, type, q]
            endkey = [domain, type, q + 'zzzzzz']
            return Location.view('locations/by_name',
                startkey=startkey,
                endkey=endkey,
                limit=LIMIT,
                reduce=False,
                include_docs=True,
            )

        locs = sorted(itertools.chain(*(get_locs(loc_type) for loc_type in loc_types)), key=lambda e: e.name)[:LIMIT]
        return HttpResponse(json.dumps(map(loc_to_payload, locs)), 'text/json')
