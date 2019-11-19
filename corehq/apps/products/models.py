import uuid
import warnings
from datetime import datetime
from decimal import Decimal

from django.db import models
from django.utils.translation import ugettext as _

import jsonfield
from couchdbkit.exceptions import ResourceNotFound

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    DecimalProperty,
    DictProperty,
    Document,
    StringProperty,
)
from dimagi.utils.couch.database import iter_docs

# move these too
from corehq.apps.commtrack.exceptions import (
    DuplicateProductCodeException,
    InvalidProductException,
)


class ProductQueriesMixin(object):

    def product_ids(self):
        return self.values_list('product_id', flat=True)

    def couch_products(self, wrapped=True):
        """
        Returns the couch products corresponding to this queryset.
        """
        ids = self.product_ids()
        products = iter_docs(Product.get_db(), ids)
        if wrapped:
            return map(Product.wrap, products)
        return products


class ProductQuerySet(ProductQueriesMixin, models.query.QuerySet):
    pass


class ProductManager(ProductQueriesMixin, models.Manager):

    def get_queryset(self):
        return ProductQuerySet(self.model, using=self._db)


class OnlyActiveProductManager(ProductManager):

    def get_queryset(self):
        return super(OnlyActiveProductManager, self).get_queryset().filter(is_archived=False)


class SQLProduct(models.Model):
    """
    A SQL based clone of couch Products.

    This is used to efficiently filter StockState and other
    SQL based queries to exclude data for archived products.
    """
    domain = models.CharField(max_length=255, db_index=True)
    product_id = models.CharField(max_length=100, db_index=True, unique=True)
    name = models.CharField(max_length=100, null=True)
    is_archived = models.BooleanField(default=False)
    code = models.CharField(max_length=100, default='', null=True)
    description = models.TextField(null=True, default='')
    category = models.CharField(max_length=100, null=True, default='')
    program_id = models.CharField(max_length=100, null=True, default='')
    cost = models.DecimalField(max_digits=20, decimal_places=5, null=True)
    units = models.CharField(max_length=100, null=True, default='')
    product_data = jsonfield.JSONField(
        default=dict,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    objects = ProductManager()
    active_objects = OnlyActiveProductManager()

    def __str__(self):
        return "{} ({})".format(self.name, self.domain)

    def __repr__(self):
        return "<SQLProduct(domain=%s, name=%s)>" % (
            self.domain,
            self.name
        )

    @classmethod
    def by_domain(cls, domain):
        return cls.objects.filter(domain=domain).all()

    @property
    def get_id(self):
        warnings.warn(
            "get_id should be changed to product_id",
            DeprecationWarning,
        )
        return self.product_id

    @property
    def _id(self):
        warnings.warn(
            "_id should be changed to product_id",
            DeprecationWarning,
        )
        return self.product_id

    @property
    def unit(self):
        warnings.warn(
            "unit should be changed to units",
            DeprecationWarning,
        )
        return self.units

    class Meta(object):
        app_label = 'products'

    def to_dict(self):
        from corehq.apps.commtrack.util import encode_if_needed
        product_dict = {}

        product_dict['id'] = self.product_id
        product_dict['product_id'] = self.code  # This seems wrong

        for attr in PRODUCT_EXPORT_ATTRS:
            real_attr = attr[0] if isinstance(attr, tuple) else attr
            product_dict[real_attr] = encode_if_needed(
                getattr(self, real_attr)
            )

        return product_dict

    def archive(self):
        """
        Mark a product as archived. This will cause it (and its data)
        to not show up in default Couch and SQL views.
        """
        self.is_archived = True
        self.save()

    def unarchive(self):
        """
        Unarchive a product, causing it (and its data) to show
        up in Couch and SQL views again.
        """
        if self.code:
            if SQLProduct.active_objects.filter(domain=self.domain, code=self.code).exists():
                raise DuplicateProductCodeException()
        self.is_archived = False
        self.save()

    @classmethod
    def from_excel(cls, row, custom_data_validator):
        if not row:
            return None

        id = row.get('id')
        if id:
            try:
                product = cls.objects.get(location_id=id)
            except ResourceNotFound:
                raise InvalidProductException(
                    _("Product with ID '{product_id}' could not be found!").format(product_id=id)
                )
        else:
            product = cls()

        product.code = str(row.get('product_id') or uuid.uuid4().hex)

        for attr in PRODUCT_EXPORT_ATTRS:
            key = attr[0] if isinstance(attr, tuple) else attr
            if key in row:
                val = row[key]
                if val is None:
                    val = ''
                if isinstance(attr, tuple):
                    val = attr[1](val)
                setattr(product, key, val)
            else:
                break

        if not product.code:
            raise InvalidProductException(_('Product ID is a required field and cannot be blank!'))
        if not product.name:
            raise InvalidProductException(_('Product name is a required field and cannot be blank!'))

        custom_data = row.get('data', {})
        error = custom_data_validator(custom_data)
        if error:
            raise InvalidProductException(error)

        product.product_data = custom_data
        product.product_data.update(row.get('uncategorized_data', {}))

        return product


PRODUCT_EXPORT_ATTRS = [
    ('name', str),
    ('unit', str),
    'description',
    'category',
    ('program_id', str),
    ('cost', lambda a: Decimal(a) if a else None),
]
