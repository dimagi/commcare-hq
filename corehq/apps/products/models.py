from couchdbkit.exceptions import ResourceNotFound
from dimagi.ext.couchdbkit import (
    Document,
    StringProperty,
    DecimalProperty,
    DictProperty,
    BooleanProperty,
    DateTimeProperty,
)
from datetime import datetime
from decimal import Decimal
from django.db import models
from django.utils.translation import ugettext as _
import json_field

# move these too
from corehq.apps.commtrack.exceptions import InvalidProductException, DuplicateProductCodeException


class Product(Document):
    """
    A product, e.g. "coartem" or "tylenol"
    """
    domain = StringProperty()
    name = StringProperty()
    unit = StringProperty()
    code_ = StringProperty()  # todo: why the hell is this code_ and not code
    description = StringProperty()
    category = StringProperty()
    program_id = StringProperty()
    cost = DecimalProperty()
    product_data = DictProperty()
    is_archived = BooleanProperty(default=False)
    last_modified = DateTimeProperty()

    @classmethod
    def wrap(cls, data):
        from corehq.apps.groups.models import dt_no_Z_re
        # If "Z" is missing because of the Aug 2014 migration, then add it.
        # cf. Group class
        last_modified = data.get('last_modified')
        if last_modified and dt_no_Z_re.match(last_modified):
            data['last_modified'] += 'Z'
        return super(Product, cls).wrap(data)

    @classmethod
    def save_docs(cls, docs, use_uuids=True, all_or_nothing=False, codes_by_domain=None):
        from corehq.apps.commtrack.util import generate_code

        codes_by_domain = codes_by_domain or {}

        def get_codes(domain):
            if domain not in codes_by_domain:
                codes_by_domain[domain] = SQLProduct.objects.filter(domain=domain)\
                    .values_list('code', flat=True).distinct()
            return codes_by_domain[domain]

        for doc in docs:
            if not doc['code_']:
                doc['code_'] = generate_code(
                    doc['name'],
                    get_codes(doc['domain'])
                )

        super(Product, cls).save_docs(docs, use_uuids, all_or_nothing)

    bulk_save = save_docs

    def sync_to_sql(self):
        properties_to_sync = [
            ('product_id', '_id'),
            'domain',
            'name',
            'is_archived',
            ('code', 'code_'),
            'description',
            'category',
            'program_id',
            'cost',
            ('units', 'unit'),
            'product_data',
        ]

        # sync properties to SQL version
        sql_product, _ = SQLProduct.objects.get_or_create(
            product_id=self._id
        )

        for prop in properties_to_sync:
            if isinstance(prop, tuple):
                sql_prop, couch_prop = prop
            else:
                sql_prop = couch_prop = prop

            if hasattr(self, couch_prop):
                setattr(sql_product, sql_prop, getattr(self, couch_prop))

        sql_product.save()

    def save(self, *args, **kwargs):
        """
        Saving a couch version of Product will trigger
        one way syncing to the SQLProduct version of this
        product.
        """
        # mark modified time stamp for selective syncing
        self.last_modified = datetime.utcnow()

        # generate code if user didn't specify one
        if not self.code:
            from corehq.apps.commtrack.util import generate_code
            self.code = generate_code(
                self.name,
                SQLProduct.objects
                    .filter(domain=self.domain)
                    .values_list('code', flat=True)
                    .distinct()
            )

        result = super(Product, self).save(*args, **kwargs)

        self.sync_to_sql()

        return result

    @property
    def code(self):
        return self.code_

    @code.setter
    def code(self, val):
        self.code_ = val.lower() if val else None

    @classmethod
    def get_by_code(cls, domain, code):
        if not code:
            return None
        result = cls.view("commtrack/product_by_code",
                          key=[domain, code.lower()],
                          include_docs=True).first()
        return result

    @classmethod
    def by_program_id(cls, domain, prog_id, wrap=True, **kwargs):
        kwargs.update(dict(
            view_name='commtrack/product_by_program_id',
            key=[domain, prog_id],
            include_docs=True
        ))
        if wrap:
            return Product.view(**kwargs)
        else:
            return [row["doc"] for row in Product.view(wrap_doc=False, **kwargs)]

    @classmethod
    def by_domain(cls, domain, wrap=True, include_archived=False, **kwargs):
        """
        Gets all products in a domain.

        By default this filters out any archived products.
        WARNING: this doesn't paginate correctly; it filters after the query
        If you need pagination, use SQLProduct instead
        """
        kwargs.update(dict(
            view_name='commtrack/products',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        ))
        if wrap:
            products = Product.view(**kwargs)
            if not include_archived:
                return filter(lambda p: not p.is_archived, products)
            else:
                return products
        else:
            if not include_archived:
                return [
                    row["doc"] for row in Product.view(
                        wrap_doc=False,
                        **kwargs
                    ) if not row["doc"].get('is_archived', False)
                ]
            else:
                return [
                    row["doc"] for row in Product.view(
                        wrap_doc=False,
                        **kwargs
                    )
                ]

    @classmethod
    def archived_by_domain(cls, domain, wrap=True, **kwargs):
        products = cls.by_domain(domain, wrap, kwargs)
        if wrap:
            return filter(lambda p: p.is_archived, products)
        else:
            return [p for p in products if p.get('is_archived', False)]

    @classmethod
    def ids_by_domain(cls, domain):
        """
        Gets all product ids in a domain.
        """
        view_results = Product.get_db().view('commtrack/products',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=False,
        )
        return [row['id'] for row in view_results]

    @classmethod
    def count_by_domain(cls, domain):
        """
        Gets count of products in a domain
        """
        # todo: we should add a reduce so we can get this out of couch
        return len(cls.ids_by_domain(domain))

    @classmethod
    def _export_attrs(cls):
        return [
            ('name', unicode),
            ('unit', unicode),
            'description',
            'category',
            ('program_id', str),
            ('cost', lambda a: Decimal(a) if a else None),
        ]

    def to_dict(self):
        from corehq.apps.commtrack.util import encode_if_needed
        product_dict = {}

        product_dict['id'] = self._id
        product_dict['product_id'] = self.code_

        for attr in self._export_attrs():
            real_attr = attr[0] if isinstance(attr, tuple) else attr
            product_dict[real_attr] = encode_if_needed(
                getattr(self, real_attr)
            )

        return product_dict

    def custom_property_dict(self):
        from corehq.apps.commtrack.util import encode_if_needed
        property_dict = {}

        for prop, val in self.product_data.iteritems():
            property_dict['data: ' + prop] = encode_if_needed(val)

        return property_dict

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
            if SQLProduct.objects.filter(code=self.code, is_archived=False).exists():
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
                p = cls.get(id)
            except ResourceNotFound:
                raise InvalidProductException(
                    _("Product with ID '{product_id}' could not be found!").format(product_id=id)
                )
        else:
            p = cls()

        p.code = str(row.get('product_id') or '')

        for attr in cls._export_attrs():
            key = attr[0] if isinstance(attr, tuple) else attr
            if key in row:
                val = row[key]
                if val is None:
                    val = ''
                if isinstance(attr, tuple):
                    val = attr[1](val)
                setattr(p, key, val)
            else:
                break

        if not p.code:
            raise InvalidProductException(_('Product ID is a required field and cannot be blank!'))
        if not p.name:
            raise InvalidProductException(_('Product name is a required field and cannot be blank!'))

        custom_data = row.get('data', {})
        error = custom_data_validator(custom_data)
        if error:
            raise InvalidProductException(error)

        p.product_data = custom_data
        p.product_data.update(row.get('uncategorized_data', {}))

        return p


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
    product_data = json_field.JSONField(
        default={},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return u"{} ({})".format(self.name, self.domain)

    def __repr__(self):
        return "<SQLProduct(domain=%s, name=%s)>" % (
            self.domain,
            self.name
        )

    @classmethod
    def by_domain(cls, domain):
        return cls.objects.filter(domain=domain).all()

    class Meta:
        app_label = 'products'
