from corehq.apps.api.resources.v0_4 import XFormInstanceResource
from corehq.apps.zapier.util import remove_advanced_fields


class ZapierXFormInstanceResource(XFormInstanceResource):

    def dehydrate(self, bundle):
        remove_advanced_fields(bundle.data)
        return bundle
