from corehq.apps.commtrack.models import Product, CommtrackConfig,\
    CommtrackActionConfig, SupplyPointType, SupplyPointCase

"""
helper code to populate the various commtrack models, for ease of
development/testing, before we have proper UIs and imports
"""

PRODUCTS = [
    ('PSI kit', 'k'),
    ('non-PSI kit', 'nk'),
    ('ORS', 'x'),
    ('Zinc', 'z'),
]


def psi_one_time_setup(domain):
    commtrack_enable_domain(domain)
    make_psi_config(domain.name)
    make_products(domain.name, PRODUCTS)


def commtrack_enable_domain(domain):
    domain.commtrack_enabled = True
    domain.save()


def make_products(domain, products):
    for name, code in products:
        make_product(domain, name, code)


def make_product(domain, name, code):
    p = Product()
    p.domain = domain
    p.name = name
    p.code = code.lower()
    p.save()
    return p

def make_supply_point(domain, location, owner_id=None):
    return SupplyPointCase.create_from_location(domain, location, owner_id)

def make_psi_config(domain):
    c = CommtrackConfig(
        domain=domain,
        multiaction_enabled=True,
        multiaction_keyword='s',
        actions=[
            CommtrackActionConfig(
                action_type='stockedoutfor',
                keyword='d',
                caption='Stock-out Days'
            ),
            CommtrackActionConfig(
                action_type='receipts',
                keyword='r',
                caption='Other Receipts'
            ),
            CommtrackActionConfig(
                action_type='stockonhand',
                keyword='b',
                caption='Balance'
            ),
            CommtrackActionConfig(
                action_type='receipts',
                name='sales',
                keyword='p',
                caption='Placements'
            ),
        ],
        supply_point_types=[
            SupplyPointType(name='CHC', categories=['Public']),
            SupplyPointType(name='PHC', categories=['Public']),
            SupplyPointType(name='SC', categories=['Public']),
            SupplyPointType(name='MBBS', categories=['Private']),
            SupplyPointType(name='Pediatrician', categories=['Private']),
            SupplyPointType(name='AYUSH', categories=['Private']),
            SupplyPointType(name='Medical Store / Chemist', categories=['Traditional']),
            SupplyPointType(name='RP', categories=['Traditional']),
            SupplyPointType(name='Asha', categories=['Frontline Workers']),
            SupplyPointType(name='AWW', categories=['Public', 'Frontline Workers']),
            SupplyPointType(name='NGO', categories=['Non-traditional']),
            SupplyPointType(name='CBO', categories=['Non-traditional']),
            SupplyPointType(name='SHG', categories=['Non-traditional']),
            SupplyPointType(name='Pan Store', categories=['Traditional']),
            SupplyPointType(name='General Store', categories=['Traditional']),
        ]
    )
    c.save()
    return c
