from collections import defaultdict
from itertools import product
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseNotFound
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.commtrack.util import get_or_make_def_program

from corehq.apps.domain.decorators import require_superuser, domain_admin_required, require_previewer, login_and_domain_required
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.management.commands import bootstrap_psi
from corehq.apps.commtrack.models import Product, Program
from corehq.apps.commtrack.forms import ProductForm, ProgramForm, ConsumptionForm
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.locations.models import Location
from dimagi.utils.decorators.memoized import memoized
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

@domain_admin_required
def default(request, domain):
    if not (request.project and request.project.commtrack_enabled):
        raise Http404()
    return HttpResponseRedirect(reverse(ProductListView.urlname,
                                        args=[domain]))


class BaseCommTrackManageView(BaseDomainView):
    section_name = ugettext_noop("Setup")

    @property
    def section_url(self):
        return reverse('default_commtrack_setup', args=[self.domain])

    @method_decorator(domain_admin_required)  # TODO: will probably want less restrictive permission?
    def dispatch(self, request, *args, **kwargs):
        return super(BaseCommTrackManageView, self).dispatch(request, *args, **kwargs)


class DefaultConsumptionView(BaseCommTrackManageView):
    urlname = 'update_default_consumption'
    template_name = 'commtrack/manage/default_consumption.html'
    page_title = ugettext_noop("Manage Default Consumption")

    @property
    @memoized
    def consumption_form(self):
        if self.request.method == 'POST':
            return ConsumptionForm(self.domain, self.request.POST)
        return ConsumptionForm(self.domain)

    @property
    def page_context(self):
        return {
            'form': self.consumption_form,
        }

    def post(self, request, *args, **kwargs):
        if self.consumption_form.is_valid():
            self.consumption_form.save()
            messages.success(request, _("Default consumption values updated"))
            return HttpResponseRedirect(
                reverse(DefaultConsumptionView.urlname, args=[self.domain])
            )
        return self.get(request, *args, **kwargs)


class ProductListView(BaseCommTrackManageView):
    # todo mobile workers shares this type of view too---maybe there should be a class for this?
    urlname = 'commtrack_product_list'
    template_name = 'commtrack/manage/products.html'
    page_title = ugettext_noop("Manage Products")

    DEFAULT_LIMIT = 10

    @property
    def page(self):
        return self.request.GET.get('page', 1)

    @property
    def limit(self):
        return self.request.GET.get('limit', self.DEFAULT_LIMIT)

    @property
    def show_inactive(self):
        return json.loads(self.request.GET.get('show_inactive', 'false'))

    @property
    def total(self):
        return len(Product.by_domain(self.domain))

    @property
    def page_context(self):
        return {
            'data_list': {
                'page': self.page,
                'limit': self.limit,
                'total': self.total
            },
            'show_inactive': self.show_inactive,
            'pagination_limit_options': range(self.DEFAULT_LIMIT, 51, self.DEFAULT_LIMIT)
        }


class FetchProductListView(ProductListView):
    urlname = 'commtrack_product_fetch'

    def skip(self):
        return (int(self.page) - 1) * int(self.limit)

    @property
    def product_data(self):
        data = []
        products = Product.by_domain(domain=self.domain, limit=self.limit, skip=self.skip())
        for p in products:
            if p.program_id:
                program = Program.get(p.program_id)
            else:
                program = get_or_make_def_program(self.domain)
                p.program_id = program.get_id
                p.save()

            info = p._doc
            info['program'] = program.name
            info['edit_url'] = reverse('commtrack_product_edit', kwargs={'domain': self.domain, 'prod_id': p._id})
            data.append(info)
        return data

    def get(self, request, *args, **kwargs):
        return HttpResponse(json.dumps({
            'success': True,
            'current_page': self.page,
            'data_list': self.product_data,
        }), 'text/json')


class NewProductView(BaseCommTrackManageView):
    urlname = 'commtrack_product_new'
    page_title = ugettext_noop("New Product")
    template_name = 'commtrack/manage/product.html'

    @property
    @memoized
    def product(self):
        return Product(domain=self.domain)

    @property
    def parent_pages(self):
        return [{
            'title': ProductListView.page_title,
            'url': reverse(ProductListView.urlname, args=[self.domain]),
        }]

    @property
    @memoized
    def new_product_form(self):
        if self.request.method == 'POST':
            return ProductForm(self.product, self.request.POST)
        return ProductForm(self.product)

    @property
    def page_context(self):
        return {
            'product': self.product,
            'form': self.new_product_form,
        }

    def post(self, request, *args, **kwargs):
        if self.new_product_form.is_valid():
            self.new_product_form.save()
            messages.success(request, _("Product saved!"))
            return HttpResponseRedirect(reverse(ProductListView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class EditProductView(NewProductView):
    urlname = 'commtrack_product_edit'
    page_title = ugettext_noop("Edit Product")

    @property
    def product_id(self):
        try:
            return self.kwargs['prod_id']
        except KeyError:
            raise Http404()

    @property
    @memoized
    def product(self):
        try:
            return Product.get(self.product_id)
        except ResourceNotFound:
            raise Http404()

    @property
    def page_name(self):
        return _("Edit %s") % self.product.name

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.product_id])


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


class ProgramListView(BaseCommTrackManageView):
    urlname = 'commtrack_program_list'
    template_name = 'commtrack/manage/programs.html'
    page_title = ugettext_noop("Manage Programs")

    @property
    def page_context(self):
        return {}


class FetchProgramListView(ProgramListView):
    urlname = 'commtrack_program_fetch'

    @property
    def program_data(self):
        data = []
        programs = Program.by_domain(self.domain)
        for p in programs:
            info = p._doc
            info['edit_url'] = reverse('commtrack_program_edit', kwargs={'domain': self.domain, 'prog_id': p._id})
            data.append(info)
        return data

    def get(self, request, *args, **kwargs):
        return HttpResponse(json.dumps({
            'success': True,
            'data_list': self.program_data,
        }), 'text/json')


class NewProgramView(BaseCommTrackManageView):
    urlname = 'commtrack_program_new'
    page_title = ugettext_noop("New Program")
    template_name = 'commtrack/manage/program.html'

    @property
    @memoized
    def program(self):
        return Program(domain=self.domain)

    @property
    def parent_pages(self):
        return [{
            'title': ProgramListView.page_title,
            'url': reverse(ProgramListView.urlname, args=[self.domain]),
        }]

    @property
    @memoized
    def new_program_form(self):
        if self.request.method == 'POST':
            return ProgramForm(self.program, self.request.POST)
        return ProgramForm(self.program)

    @property
    def page_context(self):
        return {
            'program': self.program,
            'form': self.new_program_form,
        }

    def post(self, request, *args, **kwargs):
        if self.new_program_form.is_valid():
            self.new_program_form.save()
            messages.success(request, _("Program saved!"))
            return HttpResponseRedirect(reverse(ProgramListView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class EditProgramView(NewProgramView):
    urlname = 'commtrack_program_edit'
    page_title = ugettext_noop("Edit Program")

    DEFAULT_LIMIT = 10

    @property
    def page(self):
        return self.request.GET.get('page', 1)

    @property
    def limit(self):
        return self.request.GET.get('limit', self.DEFAULT_LIMIT)

    @property
    def total(self):
        return len(Product.by_program_id(self.domain, self.program_id))

    @property
    def page_context(self):
        return {
            'program': self.program,
            'data_list': {
                'page': self.page,
                'limit': self.limit,
                'total': self.total
            },
            'pagination_limit_options': range(self.DEFAULT_LIMIT, 51, self.DEFAULT_LIMIT),
            'form': self.new_program_form,
        }

    @property
    def program_id(self):
        try:
            return self.kwargs['prog_id']
        except KeyError:
            raise Http404()

    @property
    @memoized
    def program(self):
        try:
            return Program.get(self.program_id)
        except ResourceNotFound:
            raise Http404()

    @property
    def page_name(self):
        return _("Edit %s") % self.program.name

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.program_id])

class FetchProductForProgramListView(EditProgramView):
    urlname = 'commtrack_product_for_program_fetch'

    def skip(self):
        return (int(self.page) - 1) * int(self.limit)

    @property
    def product_data(self):
        data = []
        products = Product.by_program_id(domain=self.domain, prog_id=self.program_id, skip=self.skip(),
                limit=self.limit)
        for p in products:
            data.append(p._doc)
        return data

    def get(self, request, *args, **kwargs):
        return HttpResponse(json.dumps({
            'success': True,
            'current_page': self.page,
            'data_list': self.product_data,
        }), 'text/json')
