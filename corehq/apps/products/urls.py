from django.urls import re_path as url

from corehq.apps.products.views import (
    EditProductView,
    FetchProductListView,
    NewProductView,
    ProductFieldsView,
    ProductImportStatusView,
    ProductListView,
    UploadProductView,
    archive_product,
    download_products,
    product_importer_job_poll,
    unarchive_product,
)

settings_urls = [
    url(r'^$', ProductListView.as_view(), name=ProductListView.urlname),
    url(r'^fields/$', ProductFieldsView.as_view(), name=ProductFieldsView.urlname),
    url(r'^list/$', FetchProductListView.as_view(), name=FetchProductListView.urlname),
    url(r'^new/$', NewProductView.as_view(), name=NewProductView.urlname),
    url(r'^upload/$', UploadProductView.as_view(), name=UploadProductView.urlname),
    url(r'^upload/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$', ProductImportStatusView.as_view(),
        name=ProductImportStatusView.urlname),
    url(r'^upload/poll/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        product_importer_job_poll, name='product_importer_job_poll'),
    url(r'^download/$', download_products, name='product_export'),
    url(r'^(?P<prod_id>[\w-]+)/$', EditProductView.as_view(), name=EditProductView.urlname),
    url(r'^archive/(?P<prod_id>[\w-]+)/$', archive_product, name='archive_product'),
    url(r'^unarchive/(?P<prod_id>[\w-]+)/$', unarchive_product, name='unarchive_product'),
]
