import json
from couchexport.writers import Excel2007ExportWriter
from couchexport.models import Format
from couchdbkit import ResourceNotFound
from corehq.apps.commtrack.util import get_or_create_default_program
from django.views.decorators.http import require_POST
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.utils.translation import ugettext as _, ugettext_noop
from django.contrib import messages
from soil.util import expose_download, get_download_context
from StringIO import StringIO
from dimagi.utils.web import json_response
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.products.tasks import import_products_async
from corehq.apps.products.models import Product
from corehq.apps.products.forms import ProductForm
from corehq.apps.commtrack.views import BaseCommTrackManageView
from corehq.apps.commtrack.util import encode_if_needed
from corehq.apps.programs.models import Program
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.custom_data_fields.views import (
    CustomDataEditor, CustomDataFieldsMixin
)
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
)


@require_POST
@domain_admin_required
def archive_product(request, domain, prod_id, archive=True):
    """
    Archive product
    """
    product = Product.get(prod_id)
    product.archive()
    return json_response({
        'success': True,
        'message': _("Product '{product_name}' has successfully been {action}.").format(
            product_name=product.name,
            action="archived",
        )
    })


@require_POST
@domain_admin_required
def unarchive_product(request, domain, prod_id, archive=True):
    """
    Unarchive product
    """
    product = Product.get(prod_id)
    product.unarchive()
    return json_response({
        'success': True,
        'message': _("Product '{product_name}' has successfully been {action}.").format(
            product_name=product.name,
            action="unarchived",
        )
    })


class ProductListView(BaseCommTrackManageView):
    # todo mobile workers shares this type of view too---maybe there should be a class for this?
    urlname = 'commtrack_product_list'
    template_name = 'products/manage/products.html'
    page_title = ugettext_noop("Products")

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
    @memoized
    def total(self):
        return Product.count_by_domain(self.domain)

    @property
    def page_context(self):
        return {
            'data_list': {
                'page': self.page,
                'limit': self.limit,
                'total': self.total
            },
            'archive_help_text': _(
                "Archive a product to stop showing data for it in \
                reports and on mobile applications. Archiving is \
                completely reversible, so you can always reactivate \
                it later."
            ),
            'show_inactive': self.show_inactive,
            'pagination_limit_options': range(self.DEFAULT_LIMIT, 51, self.DEFAULT_LIMIT)
        }


class FetchProductListView(ProductListView):
    urlname = 'commtrack_product_fetch'

    def skip(self):
        return (int(self.page) - 1) * int(self.limit)

    def get_archive_text(self, is_archived):
        if is_archived:
            return _("This will re-activate the product, and the product will show up in reports again.")
        return _("As a result of archiving, this product will no longer appear in reports. "
                 "This action is reversable; you can reactivate this product by viewing "
                 "Show Archived Products and clicking 'Unarchive'.")

    @property
    def product_data(self):
        data = []
        if self.show_inactive:
            products = Product.archived_by_domain(
                domain=self.domain,
                limit=self.limit,
                skip=self.skip(),
            )
        else:
            products = Product.by_domain(
                domain=self.domain,
                limit=self.limit,
                skip=self.skip(),
            )

        for p in products:
            if p.program_id:
                program = Program.get(p.program_id)
            else:
                program = get_or_create_default_program(self.domain)
                p.program_id = program.get_id
                p.save()

            info = p._doc
            info['program'] = program.name
            info['edit_url'] = reverse('commtrack_product_edit', kwargs={'domain': self.domain, 'prod_id': p._id})
            info['archive_action_desc'] = self.get_archive_text(self.show_inactive)
            info['archive_action_text'] = _("Un-Archive") if self.show_inactive else _("Archive")
            info['archive_url'] = reverse(
                'unarchive_product' if self.show_inactive else 'archive_product',
                kwargs={'domain': self.domain, 'prod_id': p._id}
            )
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
    template_name = 'products/manage/product.html'

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
            'data_fields_form': self.custom_data.form,
        }

    @property
    @memoized
    def custom_data(self):
        return CustomDataEditor(
            field_view=ProductFieldsView,
            domain=self.domain,
            required_only=True,
            post_dict=self.request.POST if self.request.method == "POST" else None,
        )

    def post(self, request, *args, **kwargs):
        if all([self.new_product_form.is_valid(),
                self.custom_data.is_valid()]):
            self.product.product_data = self.custom_data.get_data_to_save()
            self.new_product_form.save(self.product)
            messages.success(request, _("Product saved!"))
            return HttpResponseRedirect(reverse(ProductListView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class UploadProductView(BaseCommTrackManageView):
    urlname = 'commtrack_upload_products'
    page_title = ugettext_noop("Import Products")
    template_name = 'products/manage/upload_products.html'

    @property
    def page_context(self):
        context = {
            'bulk_upload': {
                "download_url": reverse("product_export", args=(self.domain,)),
                "adjective": _("product"),
                "plural_noun": _("products"),
            },
        }
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context),
        })
        return context

    @property
    def parent_pages(self):
        return [{
            'title': ProductListView.page_title,
            'url': reverse(ProductListView.urlname, args=[self.domain]),
        }]

    def post(self, request, *args, **kwargs):
        upload = request.FILES.get('bulk_upload_file')
        if not upload:
            messages.error(request, _('no file uploaded'))
            return self.get(request, *args, **kwargs)
        elif not upload.name.endswith('.xlsx'):
            messages.error(request, _('please use xlsx format only'))
            return self.get(request, *args, **kwargs)

        domain = args[0]
        # stash this in soil to make it easier to pass to celery
        file_ref = expose_download(upload.read(),
                                   expiry=1*60*60)
        task = import_products_async.delay(
            domain,
            file_ref.download_id,
        )
        file_ref.set_task(task)
        return HttpResponseRedirect(
            reverse(
                ProductImportStatusView.urlname,
                args=[domain, file_ref.download_id]
            )
        )

class ProductImportStatusView(BaseCommTrackManageView):
    urlname = 'product_import_status'
    page_title = ugettext_noop('Product Import Status')

    def get(self, request, *args, **kwargs):
        context = super(ProductImportStatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse('product_importer_job_poll', args=[self.domain, kwargs['download_id']]),
            'title': _("Product Import Status"),
            'progress_text': _("Importing your data. This may take some time..."),
            'error_text': _("Problem importing data! Please try again or report an issue."),
        })
        return render(request, 'hqwebapp/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)

@login_and_domain_required
def product_importer_job_poll(request, domain, download_id,
        template="products/manage/partials/product_upload_status.html"):
    context = get_download_context(download_id, check_state=True)
    context.update({
        'on_complete_short': _('Import complete.'),
        'on_complete_long': _('Product importing has finished'),

    })
    return render(request, template, context)


def download_products(request, domain):
    def _parse_custom_properties(product):
        product_data_model = CustomDataFieldsDefinition.get_or_create(
            domain,
            ProductFieldsView.field_type
        )
        product_data_fields = [f.slug for f in product_data_model.fields]

        model_data = {}
        uncategorized_data = {}

        for prop, val in product.product_data.iteritems():
            if prop in product_data_fields:
                model_data['data: ' + prop] = encode_if_needed(val)
            else:
                uncategorized_data['uncategorized_data: ' + prop] = encode_if_needed(val)

        return model_data, uncategorized_data

    def _get_products(domain):
        for p_doc in iter_docs(Product.get_db(), Product.ids_by_domain(domain)):
            # filter out archived products from export
            if not ('is_archived' in p_doc and p_doc['is_archived']):
                yield Product.wrap(p_doc)

    def _build_row(keys, product):
        row = []
        for key in keys:
            row.append(product.get(key, '') or '')

        return row

    file = StringIO()
    writer = Excel2007ExportWriter()

    product_keys = [
        'id',
        'name',
        'unit',
        'product_id',
        'description',
        'category',
        'program_id',
        'cost',
    ]

    model_data = set()
    uncategorized_data = set()
    products = []

    for product in _get_products(domain):
        product_dict = product.to_dict()

        product_model, product_uncategorized = _parse_custom_properties(product)

        model_data.update(product_model.keys())
        uncategorized_data.update(product_uncategorized.keys())

        product_dict.update(product_model)
        product_dict.update(product_uncategorized)

        products.append(product_dict)

    keys = product_keys + list(model_data) + list(uncategorized_data)

    writer.open(
        header_table=[
            ('products', [keys])
        ],
        file=file,
    )

    for product in products:
        writer.write([('products', [_build_row(keys, product)])])

    writer.close()

    response = HttpResponse(mimetype=Format.from_format('xlsx').mimetype)
    response['Content-Disposition'] = 'attachment; filename="products.xlsx"'
    response.write(file.getvalue())
    return response


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

    @property
    @memoized
    def custom_data(self):
        return CustomDataEditor(
            field_view=ProductFieldsView,
            domain=self.domain,
            existing_custom_data=self.product.product_data,
            post_dict=self.request.POST if self.request.method == "POST" else None,
        )


class ProductFieldsView(CustomDataFieldsMixin, BaseCommTrackManageView):
    urlname = 'product_fields_view'
    field_type = 'ProductFields'
    entity_string = _("Product")
