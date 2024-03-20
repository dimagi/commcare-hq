import json
from io import BytesIO

from django.contrib import messages
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.http.response import HttpResponseServerError
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop
from django.views.decorators.http import require_POST

from couchdbkit import ResourceNotFound
from memoized import memoized

from couchexport.models import Format
from couchexport.writers import Excel2007ExportWriter
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.web import json_response
from soil.exceptions import TaskFailedError
from soil.util import expose_cached_download, get_download_context

from corehq.apps.commtrack.exceptions import DuplicateProductCodeException
from corehq.apps.commtrack.util import (
    encode_if_needed,
    get_or_create_default_program,
)
from corehq.apps.commtrack.views import BaseCommTrackManageView
from corehq.apps.custom_data_fields.edit_entity import CustomDataEditor
from corehq.apps.custom_data_fields.edit_model import CustomDataModelMixin
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
)
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.products.forms import ProductForm
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.products.tasks import import_products_async
from corehq.apps.programs.models import Program
from corehq.util.files import file_extention_from_filename


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
    try:
        product.unarchive()
    except DuplicateProductCodeException:
        success = False
        message = _("Another product is already using the Product ID '{product_id}'").format(
            product_id=product.code
        )
    else:
        success = True
        message = _("Product '{product_name}' has successfully been {action}.").format(
            product_name=product.name,
            action="unarchived",
        )
    return json_response({
        'success': success,
        'message': message,
        'product_id': prod_id
    })


class ProductListView(BaseCommTrackManageView):
    # todo mobile workers shares this type of view too---maybe there should be a class for this?
    urlname = 'commtrack_product_list'
    template_name = 'products/manage/products.html'
    page_title = gettext_noop("Products")

    DEFAULT_LIMIT = 10

    @property
    def page(self):
        return int(self.request.GET.get('page', 1))

    @property
    def limit(self):
        return int(self.request.GET.get('limit', self.DEFAULT_LIMIT))

    @property
    def show_only_inactive(self):
        return bool(json.loads(self.request.GET.get('show_inactive', 'false')))

    @property
    def product_queryset(self):
        return (SQLProduct.objects
                .filter(domain=self.domain,
                        is_archived=self.show_only_inactive)
                .order_by('name'))

    @property
    @memoized
    def total(self):
        return self.product_queryset.count()

    @property
    def page_context(self):
        return {
            'archive_help_text': _(
                "Archive a product to stop showing data for it in \
                reports and on mobile applications. Archiving is \
                completely reversible, so you can always reactivate \
                it later."
            ),
            'show_inactive': self.show_only_inactive,
            'pagination_limit_options': list(range(self.DEFAULT_LIMIT, 51, self.DEFAULT_LIMIT)),
            'program_product_options': {
                'total': self.total,
                'start_page': self.page,
                'limit': self.limit,
                'show_inactive': self.show_only_inactive,
                'list_url': reverse('commtrack_product_fetch', args=[self.domain]),
            },
        }


class FetchProductListView(ProductListView):
    urlname = 'commtrack_product_fetch'

    @property
    def product_data(self):
        start = (self.page - 1) * self.limit
        end = start + self.limit
        return list(map(self.make_product_dict, self.product_queryset[start:end]))

    def make_product_dict(self, product):
        archive_config = self.get_archive_config()
        return {
            'name': product.name,
            'product_id': product.product_id,
            'code': product.code,
            'unit': product.units,
            'description': product.description,
            'program': self.program_name(product),
            'edit_url': reverse(
                'commtrack_product_edit',
                kwargs={'domain': self.domain, 'prod_id': product.product_id}
            ),
            'archive_action_desc': archive_config['archive_text'],
            'archive_action_text': archive_config['archive_action'],
            'archive_url': reverse(
                archive_config['archive_url'],
                kwargs={'domain': self.domain, 'prod_id': product.product_id}
            ),
        }

    @property
    @memoized
    def programs_by_id(self):
        return {p._id: p.name for p in Program.by_domain(self.domain)}

    def program_name(self, product):
        if product.program_id:
            return self.programs_by_id[product.program_id]
        else:
            program = get_or_create_default_program(self.domain)
            product.program_id = program.get_id
            product.save()
            return program.name

    def get_archive_config(self):
        if self.show_only_inactive:
            return {
                'archive_action': _("Un-Archive"),
                'archive_url': 'unarchive_product',
                'archive_text': _(
                    "This will re-activate the product, and the product will "
                    "show up in reports again."
                ),
            }
        else:
            return {
                'archive_action': _("Archive"),
                'archive_url': 'archive_product',
                'archive_text': _(
                    "As a result of archiving, this product will no longer "
                    "appear in reports. This action is reversable; you can "
                    "reactivate this product by viewing Show Archived "
                    "Products and clicking 'Unarchive'."
                ),
            }

    def get(self, request, *args, **kwargs):
        return HttpResponse(json.dumps({
            'success': True,
            'current_page': int(self.page),
            'data_list': self.product_data,
        }), 'text/json')


class NewProductView(BaseCommTrackManageView):
    urlname = 'commtrack_product_new'
    page_title = gettext_noop("New Product")
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
    page_title = gettext_noop("Import Products")
    template_name = 'hqwebapp/bulk_upload.html'

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
        file_ref = expose_cached_download(
            upload.read(),
            expiry=1*60*60,
            file_extension=file_extention_from_filename(upload.name)
        )
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
    page_title = gettext_noop('Product Import Status')

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
        return render(request, 'hqwebapp/bootstrap3/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@login_and_domain_required
def product_importer_job_poll(request, domain, download_id,
                              template="products/manage/partials/product_upload_status.html"):
    try:
        context = get_download_context(download_id)
    except TaskFailedError:
        return HttpResponseServerError()

    context.update({
        'on_complete_short': _('Import complete.'),
        'on_complete_long': _('Product importing has finished'),

    })
    return render(request, template, context)


@login_and_domain_required
def download_products(request, domain):
    def _parse_custom_properties(product):
        product_data_model = CustomDataFieldsDefinition.get_or_create(
            domain,
            ProductFieldsView.field_type
        )
        product_data_fields = [f.slug for f in product_data_model.get_fields()]

        model_data = {}
        uncategorized_data = {}

        for prop, val in product.product_data.items():
            if prop in product_data_fields:
                model_data['data: ' + prop] = encode_if_needed(val)
            else:
                uncategorized_data['uncategorized_data: ' + prop] = encode_if_needed(val)

        return model_data, uncategorized_data

    def _get_products(domain):
        product_ids = SQLProduct.objects.filter(domain=domain).product_ids()
        for p_doc in iter_docs(Product.get_db(), product_ids):
            # filter out archived products from export
            if not ('is_archived' in p_doc and p_doc['is_archived']):
                yield Product.wrap(p_doc)

    def _build_row(keys, product):
        row = []
        for key in keys:
            row.append(product.get(key, '') or '')

        return row

    file = BytesIO()
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

        model_data.update(product_model)
        uncategorized_data.update(product_uncategorized)

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

    response = HttpResponse(content_type=Format.from_format('xlsx').mimetype)
    response['Content-Disposition'] = 'attachment; filename="products.xlsx"'
    response.write(file.getvalue())
    return response


class EditProductView(NewProductView):
    urlname = 'commtrack_product_edit'
    page_title = gettext_noop("Edit Product")

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


class ProductFieldsView(CustomDataModelMixin, BaseCommTrackManageView):
    urlname = 'product_fields_view'
    field_type = 'ProductFields'
    entity_string = _("Product")
    template_name = "custom_data_fields/custom_data_fields.html"
