from __future__ import absolute_import
from __future__ import unicode_literals
from nose.tools import nottest

from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition, CustomDataField
from corehq.apps.locations.models import make_location, LocationType
from corehq.apps.products.models import SQLProduct, Product
from corehq.apps.programs.models import Program
from corehq.apps.users.models import UserRole, Permissions


def assign_products_to_locations(location, products_codes_list):
    sql_location = location.sql_location
    sql_location.products = SQLProduct.objects.filter(code__in=products_codes_list, domain=sql_location.domain)
    sql_location.save()


@nottest
def create_test_products(domain):
    program = Program(domain=domain, name='HIV/AIDS', code='hiv')
    program.save()

    abacavir = Product(
        domain=domain,
        name="Abacavir 300mg",
        code_="abc",
        program_id=program.get_id,
    )
    abacavir.save()

    ali = Product(
        domain=domain,
        name="AL 20mg/120mg 1X6",
        code_="ali",
        program_id=program.get_id,
    )
    ali.save()

    al = Product(
        domain=domain,
        name="AL 20mg/120mg 4x6",
        code_="alk"
    )
    al.save()

    ad = Product(
        domain=domain,
        name="A-L Dispersible",
        code_="ad"
    )
    ad.save()

    al = Product(
        domain=domain,
        name="A-L Suspension",
        code_="al"
    )
    al.save()


@nottest
def create_test_locations(domain):
    country = make_location(name='national', site_code='ghana', location_type='country', domain=domain)
    country.save()

    crms = make_location(
        name='Central Regional Medical Store',
        site_code='crms',
        location_type='country',
        domain=domain
    )
    crms.save()

    test_region = make_location(
        name='Test Region',
        site_code='testregion',
        location_type='region',
        domain=domain,
        parent=country
    )
    test_region.save()

    test_region2 = make_location(
        name='Test Region2',
        site_code='testregion2',
        location_type='region',
        domain=domain,
        parent=country
    )
    test_region2.save()

    rsp = make_location(
        name='Test Regional Medical Store',
        site_code='rsp',
        location_type='Regional Medical Store',
        domain=domain,
        parent=test_region2
    )
    rsp.save()
    assign_products_to_locations(rsp, ["ad", "al", "mc", "ng", "mg"])

    rsp2 = make_location(
        name='Test Regional Medical Store',
        site_code='rsp2',
        location_type='Regional Medical Store',
        domain=domain,
        parent=test_region2
    )
    rsp2.save()
    assign_products_to_locations(rsp2, ["ad", "al"])

    test_district = make_location(
        name='Test District',
        site_code='testdistrict',
        location_type='district',
        domain=domain,
        parent=test_region
    )
    test_district.save()

    test_facility = make_location(
        name='Active Test hospital',
        site_code='tsactive',
        location_type='Hospital',
        domain=domain,
        parent=test_district
    )
    test_facility.save()
    assign_products_to_locations(test_facility, ["ad", "al"])


def prepare_commtrack_config(domain):
    def _make_loc_type(name, administrative=False, parent_type=None):
        return LocationType.objects.get_or_create(
            domain=domain,
            name=name,
            administrative=administrative,
            parent_type=parent_type,
        )[0]

    for location_type in LocationType.objects.by_domain(domain):
        location_type.delete()

    country = _make_loc_type(name="country", administrative=True)
    _make_loc_type(name="Central Medical Store", parent_type=country)

    region = _make_loc_type(name="region", administrative=True,
                                 parent_type=country)
    _make_loc_type(name="Teaching Hospital", parent_type=region)
    _make_loc_type(name="Regional Medical Store", parent_type=region)
    _make_loc_type(name="Regional Hospital", parent_type=region)

    district = _make_loc_type(name="district", administrative=True,
                                   parent_type=region)
    _make_loc_type(name="Clinic", parent_type=district)
    _make_loc_type(name="District Hospital", parent_type=district)
    _make_loc_type(name="Health Centre", parent_type=district)
    _make_loc_type(name="CHPS Facility", parent_type=district)
    _make_loc_type(name="Hospital", parent_type=district)
    _make_loc_type(name="Psychiatric Hospital", parent_type=district)
    _make_loc_type(name="Polyclinic", parent_type=district)
    _make_loc_type(name="facility", parent_type=district)

    config = CommtrackConfig.for_domain(domain)
    config.consumption_config.exclude_invalid_periods = True
    config.save()


def save_custom_fields(domain, definition_name, custom_fields):
    if custom_fields:
        fields_definitions = CustomDataFieldsDefinition.get_or_create(domain, definition_name)
        need_save = False
        for custom_field in custom_fields:
            name = custom_field.get('name')
            label = custom_field.get('label')
            choices = custom_field.get('choices') or []
            existing_fields = [field for field in fields_definitions.fields if field.slug == name]
            if not existing_fields:
                need_save = True
                fields_definitions.fields.append(
                    CustomDataField(
                        slug=name,
                        label=label or name,
                        is_required=False,
                        choices=choices,
                        is_multiple_choice=custom_field.get('is_multiple_choice', False)
                    )
                )
            else:
                existing_field = existing_fields[0]
                if set(existing_field.choices) != set(choices):
                    existing_field.choices = choices
                    need_save = True

        if need_save:
            fields_definitions.save()


SMS_USER_CUSTOM_FIELDS = [
    {'name': 'to'},
    {'name': 'backend'},
    {
        'name': 'role',
        'choices': [
            'In Charge', 'Nurse', 'Pharmacist', 'Laboratory Staff', 'Other', 'Facility Manager'
        ],
        'label': 'roles',
        'is_multiple_choice': True
    }
]


def prepare_custom_fields(domain):
    save_custom_fields(domain, 'UserFields', SMS_USER_CUSTOM_FIELDS)


def _create_or_edit_facility_manager_role(domain):
    facility_manager_role = UserRole.by_domain_and_name(domain, 'Facility manager')
    reports_list = [
        "corehq.apps.reports.standard.sms.MessageLogReport",
        "custom.ewsghana.reports.specific_reports.dashboard_report.DashboardReport",
        "custom.ewsghana.reports.specific_reports.stock_status_report.StockStatus",
        "custom.ewsghana.reports.specific_reports.reporting_rates.ReportingRatesReport",
        "custom.ewsghana.reports.maps.EWSMapReport"
    ]
    if facility_manager_role:
        permissions = Permissions(
            edit_web_users=True,
            view_web_users=True,
            view_roles=True,
            edit_commcare_users=True,
            view_commcare_users=True,
            edit_groups=True,
            view_groups=True,
            edit_locations=True,
            view_locations=True,
            view_reports=False,
            view_report_list=reports_list
        )
        facility_manager_role[0].permissions = permissions
        facility_manager_role[0].save()
    else:

        role = UserRole(
            domain=domain,
            permissions=Permissions(
                view_reports=False,
                edit_web_users=True,
                view_web_users=True,
                view_roles=True,
                edit_commcare_users=True,
                view_commcare_users=True,
                edit_groups=True,
                view_groups=True,
                edit_locations=True,
                view_locations=True,
                view_report_list=reports_list
            ),
            name='Facility manager'
        )
        role.save()


def _create_or_edit_administrator_role(domain):
    administrator_role = UserRole.by_domain_and_name(domain, 'Administrator')
    reports_list = [
        "corehq.apps.reports.standard.sms.MessageLogReport",
        "custom.ewsghana.reports.specific_reports.dashboard_report.DashboardReport",
        "custom.ewsghana.reports.specific_reports.stock_status_report.StockStatus",
        "custom.ewsghana.reports.specific_reports.reporting_rates.ReportingRatesReport",
        "custom.ewsghana.reports.maps.EWSMapReport",
        "custom.ewsghana.reports.email_reports.CMSRMSReport",
        "custom.ewsghana.reports.email_reports.StockSummaryReport",
        "custom.ewsghana.comparison_report.ProductsCompareReport",
        "custom.ewsghana.comparison_report.LocationsCompareReport",
        "custom.ewsghana.comparison_report.SupplyPointsCompareReport",
        "custom.ewsghana.comparison_report.WebUsersCompareReport",
        "custom.ewsghana.comparison_report.SMSUsersCompareReport"
    ]

    if administrator_role:
        permissions = Permissions(
            edit_web_users=True,
            view_web_users=True,
            view_roles=True,
            edit_commcare_users=True,
            view_commcare_users=True,
            edit_groups=True,
            view_groups=True,
            edit_locations=True,
            view_locations=True,
            view_reports=False,
            view_report_list=reports_list
        )
        administrator_role[0].permissions = permissions
        administrator_role[0].save()
    else:
        role = UserRole(
            domain=domain,
            permissions=Permissions(
                view_reports=False,
                edit_web_users=True,
                view_web_users=True,
                view_roles=True,
                edit_commcare_users=True,
                view_commcare_users=True,
                edit_groups=True,
                view_groups=True,
                edit_locations=True,
                view_locations=True,
                view_report_list=reports_list
            ),
            name='Administrator'
        )
        role.save()


def _edit_read_only_role(domain):
    read_only_role = UserRole.get_read_only_role_by_domain(domain)
    read_only_role.permissions.view_report_list = [
        "corehq.apps.reports.standard.sms.MessageLogReport",
        "custom.ewsghana.reports.specific_reports.dashboard_report.DashboardReport",
        "custom.ewsghana.reports.specific_reports.stock_status_report.StockStatus",
        "custom.ewsghana.reports.specific_reports.reporting_rates.ReportingRatesReport",
        "custom.ewsghana.reports.maps.EWSMapReport"
    ]
    read_only_role.permissions.view_reports = False
    read_only_role.save()


def _create_or_edit_web_reporter_role(domain):
    web_reporter_roles = UserRole.by_domain_and_name(domain, 'Web Reporter')
    report_list = [
        "corehq.apps.reports.standard.sms.MessageLogReport",
        "custom.ewsghana.reports.specific_reports.dashboard_report.DashboardReport",
        "custom.ewsghana.reports.specific_reports.stock_status_report.StockStatus",
        "custom.ewsghana.reports.specific_reports.reporting_rates.ReportingRatesReport",
        "custom.ewsghana.reports.maps.EWSMapReport"
    ]
    if web_reporter_roles:
        web_reporter_role = web_reporter_roles[0]
        web_reporter_role.permissions.view_reports = False
        web_reporter_role.permissions.view_report_list = report_list
        web_reporter_role.save()
    else:
        role = UserRole(
            domain=domain,
            permissions=Permissions(
                view_reports=False,
                view_report_list=report_list
            ),
            name='Web Reporter'
        )
        role.save()


def create_or_edit_roles(domain):
    _create_or_edit_facility_manager_role(domain)
    _create_or_edit_administrator_role(domain)
    _create_or_edit_web_reporter_role(domain)
    _edit_read_only_role(domain)
