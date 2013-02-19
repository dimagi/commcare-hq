from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render

from corehq.apps.domain.decorators import require_superuser, domain_admin_required
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.management.commands import bootstrap_psi
from corehq.apps.commtrack.models import Product
from corehq.apps.commtrack.forms import ProductForm
from soil.util import expose_download
import uuid
from django.core.urlresolvers import reverse
from dimagi.utils.web import get_url_base
from django.contrib import messages
from corehq.apps.commtrack.tasks import import_locations_async,\
    import_stock_reports_async
import json
from couchdbkit import ResourceNotFound

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

    return HttpResponse('<form method="post" action=""><button type="submit">Bootstrap Commtrack domain</button></form>')

@require_superuser
def location_import(request, domain):
    if request.method == "POST":
        # stash this in soil to make it easier to pass to celery
        file_ref = expose_download(request.FILES['locs'].read(),
                                   expiry=1*60*60)
        download_id = uuid.uuid4().hex
        import_locations_async.delay(download_id, domain, file_ref.download_id)
        return _async_in_progress(request, domain, download_id)

    return HttpResponse("""
<form method="post" action="" enctype="multipart/form-data">
  <div><input type="file" name="locs" /></div>
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
