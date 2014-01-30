import json
from corehq.apps.accounting.models import Feature, SoftwareProduct
from corehq.apps.accounting.utils import fmt_feature_rate_dict, fmt_product_rate_dict
from corehq.apps.hqwebapp.async_handler import BaseAsyncHandler, AsyncHandlerError


class BaseRateAsyncHandler(BaseAsyncHandler):
    """
    Subclass this for interacting with RatesManager.
    """
    allowed_actions = [
        'apply',
        'create',
    ]

    @property
    def name(self):
        return self.data.get('name')

    @property
    def rate_type(self):
        return self.data.get('rate_type')

    @property
    def rate_id(self):
        return self.data.get('rate_id')

    @property
    def create_response(self):
        raise NotImplementedError("create_response is required")

    @property
    def apply_response(self):
        raise NotImplementedError("apply_response is required")


class FeatureRateAsyncHandler(BaseRateAsyncHandler):
    slug = 'features_handler'

    @property
    def create_response(self):
        new_feature, is_new = Feature.objects.get_or_create(
            name=self.name,
            feature_type=self.rate_type,
        )
        if not is_new:
            raise AsyncHandlerError("Feature '%s' already exists, and likely already "
                                    "in this Software Plan Version." % new_feature.name)
        return fmt_feature_rate_dict(new_feature)

    @property
    def apply_response(self):
        try:
            feature = Feature.objects.get(id=self.rate_id)
            return fmt_feature_rate_dict(feature)
        except Feature.DoesNotExist:
            raise AsyncHandlerError("could not find an existing feature")


class SoftwareProductRateAsyncHandler(BaseRateAsyncHandler):
    slug = 'products_handler'

    @property
    def create_response(self):
        new_product, is_new = SoftwareProduct.objects.get_or_create(
            name=self.name,
            product_type=self.rate_type
        )
        if not is_new:
            raise AsyncHandlerError("Product '%s' already exists, and likely already "
                                    "in this Software Plan Version." % new_product.name)
        return fmt_product_rate_dict(new_product)

    @property
    def apply_response(self):
        try:
            product = SoftwareProduct.objects.get(id=self.rate_id)
            return fmt_product_rate_dict(product)
        except SoftwareProduct.DoesNotExist:
            raise AsyncHandlerError("could not find an existing product")


class Select2RateAsyncHandler(BaseAsyncHandler):
    """
    For interacting with Select2FieldHandler
    """
    slug = 'select2_rate'
    allowed_actions = [
        'feature_id',
        'product_id',
    ]

    @property
    def search_string(self):
        return self.data.get('searchString')

    @property
    def existing(self):
        return self.data.getlist('existing[]')

    @property
    def feature_id_response(self):
        features = Feature.objects
        if self.existing:
            features = features.exclude(name__in=self.existing)
        if self.search_string:
            features = features.filter(name__startswith=self.search_string)
        return [(f.id, f.name, f.feature_type) for f in features.all()]

    @property
    def product_id_response(self):
        products = SoftwareProduct.objects
        if self.existing:
            products = products.exclude(name__in=self.existing)
        if self.search_string:
            products = products.filter(name__startswith=self.search_string)
        return [(p.id, p.name, p.product_type) for p in products.all()]

    def _fmt_success(self, response):
        return json.dumps([
            {
                'id': r[0],
                'name': r[1],
                'rate_type': r[2],
                'text': '%s (%s)' % (r[1], r[2]),
                'isExisting': True,
            } for r in response])
