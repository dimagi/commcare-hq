from couchdbkit import ResourceNotFound
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.const import RequisitionStatus
from corehq.apps.commtrack.models import SupplyPointCase, StockState, CommtrackConfig
from corehq.apps.products.models import Product
from dimagi.ext.couchdbkit import StringProperty, DateTimeProperty
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext_lazy as _


class RequisitionCase(CommCareCase):
    """
    A wrapper around CommCareCases to get more built in functionality
    specific to requisitions.
    """
    class Meta:
        # This is necessary otherwise syncdb will confuse this app with casexml
        app_label = "commtrack"

    requisition_status = StringProperty()

    # TODO none of these properties are supported on mobile currently
    # we need to discuss what will be eventually so we know what we need
    # to support here
    requested_on = DateTimeProperty()
    approved_on = DateTimeProperty()
    fulfilled_on = DateTimeProperty()
    received_on = DateTimeProperty()
    requested_by = StringProperty()
    approved_by = StringProperty()
    fulfilled_by = StringProperty()
    received_by = StringProperty()

    @memoized
    def get_location(self):
        try:
            return SupplyPointCase.get(self.indices[0].referenced_id).location
        except ResourceNotFound:
            return None

    @memoized
    def get_requester(self):
        # TODO this doesn't get set by mobile yet
        # if self.requested_by:
        #     return CommCareUser.get(self.requested_by)
        return None

    def sms_format(self):
        if self.requisition_status == RequisitionStatus.REQUESTED:
            section = 'ct-requested'
        elif self.requisition_status == RequisitionStatus.APPROVED:
            section = 'ct-approved'
        else:
            section = 'stock'

        formatted_strings = []
        states = StockState.objects.filter(
            case_id=self._id,
            section_id=section
        )
        for state in states:
            product = Product.get(state.product_id)
            formatted_strings.append(
                '%s:%d' % (product.code, state.stock_on_hand)
            )
        return ' '.join(sorted(formatted_strings))

    def get_next_action(self):
        req_config = CommtrackConfig.for_domain(self.domain).requisition_config
        return req_config.get_next_action(
            RequisitionStatus.to_action_type(self.requisition_status)
        )

    @classmethod
    def get_by_external_id(cls, domain, external_id):
        # only used by openlmis
        raise NotImplementedError()

    @classmethod
    def get_display_config(cls):
        return [
            {
                "layout": [
                    [
                        {
                            "name": _("Status"),
                            "expr": "requisition_status"
                        }
                    ],
                ]
            },
            {
                "layout": [
                    [
                        {
                            "name": _("Requested On"),
                            "expr": "requested_on",
                            "parse_date": True
                        },
                        {
                            "name": _("requested_by"),
                            "expr": "requested_by"
                        }
                    ],
                    [
                        {
                            "name": _("Approved On"),
                            "expr": "approved_on",
                            "parse_date": True
                        },
                        {
                            "name": _("approved_by"),
                            "expr": "approved_by"
                        }
                    ],
                    [
                        {
                            "name": _("Received On"),
                            "expr": "received_on",
                            "parse_date": True
                        },
                        {
                            "name": _("received_by"),
                            "expr": "received_by"
                        }
                    ]
                ]
            }
        ]
