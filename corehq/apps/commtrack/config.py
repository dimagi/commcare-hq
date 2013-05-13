from django.utils.translation import ugettext as _

from . import const

# it would be better if we made a CommtrackDomain subclass of Domain
def get_case_display(case):
    return {
        const.SUPPLY_POINT_CASE_TYPE: SUPPLY_POINT_DISPLAY,
        const.SUPPLY_POINT_PRODUCT_CASE_TYPE: SUPPLY_POINT_PRODUCT_DISPLAY,
        const.REQUISITION_CASE_TYPE: REQUISITION_DISPLAY
    }.get(case.type)


# all disabled for now by short-circuiting with None
SUPPLY_POINT_DISPLAY = None and [
    {
        "layout": [
            [
                {
                    "expr": "name",
                    "name": _("Name"),
                },
                {
                    "expr": "type",
                    "name": _("Type"),
                },
                {
                    "expr": "code",
                    "name": _("Code"),
                },
                {
                    "expr": "last_reported",
                    "name": _("Last Reported"),
                },
            ],
            [
                {
                    "expr": "location",
                    "name": _("Location"),
                },
                {
                    "expr": "owner_id",
                    "name": _("Group"),
                    "format": '<span data-field="owner_id">{0}</span>',
                },
            ],
        ],
    }
]

SUPPLY_POINT_PRODUCT_DISPLAY = None and [
    {
        "layout": [
            [
                {
                    "name": _("Supply Point"),
                    "expr": "supply_point"
                },
                {
                    "name": _("Product"),
                    "expr": "product"
                },
                {
                    "name": _("Months until stockout"),
                    "expr": "months_until_stockout"
                },
                {
                    "name": _("Stockout duration in months"),
                    "expr": "stockout_duration_in_months"
                }
            ],
            [
                {
                    "name": _("Current stock"),
                    "expr": "current_stock"
                },
                {
                    "name": _("Monthly consumption"),
                    "expr": "monthly_consumption"
                },
                {
                    "name": _("Emergency level"),
                    "expr": "emergency_level"
                },
                {
                    "name": _("Max level"),
                    "expr": "max_level"
                }
            ],
            [
                {
                    "name": _("Date of last report"),
                    "expr": "date_of_last_report"
                }
            ]
        ],
    }
]

REQUISITION_DISPLAY = None and [
    {
        "layout": [
            [
                {
                    "name": _("Supply Point"),
                    "expr": "supply_point"
                }
            ],
            [
                {
                    "name": _("Product"),
                    "expr": "product_id"
                }
            ],
            [
                {
                    "name": _("Status"),
                    "expr": "requisition_status"
                }
            ],
            [
                {
                    "name": _("Balance"),
                    "expr": "balance"
                }
            ]
        ]
    },
    {
        "layout": [
            [ 
                {
                    "name": _("Amount Requested"),
                    "expr": "amount_requested",
                },
                {
                    "name": _("Requested On"),
                    "expr": "requested_on"
                }
            ],
            [
                {
                    "name": _("Amount Approved"),
                    "expr": "amount_approved",
                },
                {
                    "name": _("Approved On"),
                    "expr": "approved_on"
                }
            ],
            [
                {
                    "name": _("Amount Received"),
                    "expr": "amount_Received"
                },
                {
                    "name": _("Received On"),
                    "expr": "received_on"
                }
            ]
        ]
    }
]
