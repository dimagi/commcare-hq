from fluff.filters import ANDFilter, ORFilter, NOTFilter, CustomFilter
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.groups.models import Group
from corehq.fluff.calculators.xform import IN_MULTISELECT, IntegerPropertyReference
from couchforms.models import XFormInstance
from .filters import ALL_CVSU_GROUP
import fluff
from corehq.fluff.calculators import xform as xcalc
from corehq.fluff.calculators import case as ccalc
from fluff.models import SimpleCalculator

REPORT_INCIDENT_XMLNS = 'http://openrosa.org/formdesigner/A12E46B1-7ED8-4DE3-B7BB-358219CC6994'
FOLLOWUP_FORM_XMLNS = 'http://openrosa.org/formdesigner/9457DE46-E640-4F6E-AD9A-F9AC9FDA35E6'
IGA_FORM_XMLNS = 'http://openrosa.org/formdesigner/B4BAF20B-4337-409D-A446-FD4A0C8D5A9A'
OUTREACH_FORM_XMLNS = 'http://openrosa.org/formdesigner/B5C415BB-456B-49BE-A7AF-C5E7C9669E34'


get_user_id = lambda form: form.metadata.userID


@memoized
def get_group_id(form):
    user_id = get_user_id(form)
    groups = Group.by_user(user_id, wrap=False)
    for g in groups:
        if g != ALL_CVSU_GROUP:
            return g


def date_reported(form):
    return form.form.get('date_reported', form.received_on)


def date_provided(form):
    return form.form.get('mediation_provided_date', form.received_on)


def date_mediated(form):
    date = form.form.get('mediation_date', form.received_on)
    return date or form.received_on  # some forms empty strings


def date_reported_mediated(form):
    if form.xmlns == FOLLOWUP_FORM_XMLNS:
        return date_mediated(form)
    else:
        return date_reported(form)


def date_reported_provided_mediated(form):
    if form.xmlns == FOLLOWUP_FORM_XMLNS:
        return date_mediated(form)
    elif ORFilter([filter_action('immediate_referral'), filter_action('actions_other')]).filter(form):
        return date_reported(form)
    else:
        return date_provided(form)


def get_age(form):
    return form.form.get('victim_age', None)


def get_sex(form):
    return form.form.get('victim_sex', None)

@memoized
def filter_action(action):
    return xcalc.FormPropertyFilter(
        xmlns=REPORT_INCIDENT_XMLNS,
        property_path='form/actions_to_resolve_case',
        property_value=action
    )


@memoized
def filter_service(service):
    return xcalc.FormPropertyFilter(
        xmlns=REPORT_INCIDENT_XMLNS,
        operator=IN_MULTISELECT,
        property_path='form/immediate_services',
        property_value=service
    )


@memoized
def filter_outcome(outcome, xmlns=None):
    if xmlns:
        return xcalc.FormPropertyFilter(
            xmlns=xmlns,
            property_path='form/mediation_outcome',
            property_value=outcome
        )
    else:
        return ORFilter([
            xcalc.FormPropertyFilter(
                xmlns=REPORT_INCIDENT_XMLNS,
                property_path='form/mediation_outcome',
                property_value=outcome
            ),
            xcalc.FormPropertyFilter(
                xmlns=FOLLOWUP_FORM_XMLNS,
                property_path='form/mediation_outcome',
                property_value=outcome
            )
        ])


@memoized
def filter_immediate_referral_org(org):
    return xcalc.FormPropertyFilter(
        xmlns=REPORT_INCIDENT_XMLNS,
        operator=IN_MULTISELECT,
        property_path='form/immediate_referral_organisation',
        property_value=org
    )


@memoized
def filter_referral_org(org):
    return ORFilter([
        xcalc.FormPropertyFilter(
            xmlns=REPORT_INCIDENT_XMLNS,
            operator=IN_MULTISELECT,
            property_path='form/mediation_referral',
            property_value=org
        ),
        xcalc.FormPropertyFilter(
            xmlns=FOLLOWUP_FORM_XMLNS,
            operator=IN_MULTISELECT,
            property_path='form/mediation_referral',
            property_value=org
        )
    ])

@memoized
def filter_abuse(category):
    return xcalc.FormPropertyFilter(
        xmlns=REPORT_INCIDENT_XMLNS,
        operator=IN_MULTISELECT,
        property_path='form/abuse_category',
        property_value=category
    )


class UnicefMalawiFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    document_filter = ANDFilter([
        NOTFilter(xcalc.FormPropertyFilter(xmlns='http://openrosa.org/user-registration')),
        NOTFilter(xcalc.FormPropertyFilter(xmlns='http://openrosa.org/user/registration')),
        NOTFilter(xcalc.FormPropertyFilter(xmlns='http://code.javarosa.org/devicereport')),
        CustomFilter(lambda f: get_user_id(f) != 'demo_user'),
        CustomFilter(lambda f: get_group_id(f)),
    ])

    domains = ('cvsulive',)
    group_by = (
        'domain',
        fluff.AttributeGetter('user_id', get_user_id),
        fluff.AttributeGetter('group_id', get_group_id),
        fluff.AttributeGetter('age', get_age),
        fluff.AttributeGetter('sex', get_sex),
    )
    group_by_type_map = {
        'age': fluff.TYPE_INTEGER
    }

    # ---------------------------------------------------------------------
    # incident resolution
    # ---------------------------------------------------------------------

    resolution_resolved_at_cvsu = SimpleCalculator(
        date_provider=date_provided,
        filter=ORFilter([
            ANDFilter([filter_action('mediation_provided'), filter_outcome('resolved', REPORT_INCIDENT_XMLNS)]),
            filter_outcome('resolved', FOLLOWUP_FORM_XMLNS)
        ])
    )

    resolution_unresolved = SimpleCalculator(
        date_provider=date_provided,
        filter=ORFilter([
            ANDFilter([filter_action('mediation_provided'), filter_outcome('unresolved', REPORT_INCIDENT_XMLNS)]),
            filter_outcome('unresolved', FOLLOWUP_FORM_XMLNS)
        ])
    )

    resolution_case_withdrawn = SimpleCalculator(
        date_provider=date_provided,
        filter=ORFilter([
            ANDFilter([filter_action('mediation_provided'), filter_outcome('case_withdrawn', REPORT_INCIDENT_XMLNS)]),
            filter_outcome('case_withdrawn', FOLLOWUP_FORM_XMLNS)
        ])
    )

    resolution_referred_ta = SimpleCalculator(
        date_provider=date_reported_provided_mediated,
        filter=ORFilter([
            ANDFilter([filter_action('immediate_referral'), filter_immediate_referral_org('ta')]),
            ANDFilter([filter_outcome('mediation_outcome_referred'), filter_referral_org('ta')])
        ])
    )

    resolution_referral_ta_court = SimpleCalculator(
        date_provider=date_reported_provided_mediated,
        filter=ORFilter([
            ANDFilter([filter_action('immediate_referral'), filter_immediate_referral_org('ta_court')]),
            ANDFilter([filter_outcome('mediation_outcome_referred'), filter_referral_org('ta_court')])
        ])
    )

    resolution_referral_police = SimpleCalculator(
        date_provider=date_reported_provided_mediated,
        filter=ORFilter([
            ANDFilter([filter_action('immediate_referral'), filter_immediate_referral_org('police')]),
            ANDFilter([filter_outcome('mediation_outcome_referred'), filter_referral_org('med_ref_police')])
        ])
    )

    resolution_referral_social_welfare = SimpleCalculator(
        date_provider=date_reported_provided_mediated,
        filter=ORFilter([
            ANDFilter([filter_action('immediate_referral'), filter_immediate_referral_org('social_welfare')]),
            ANDFilter([filter_outcome('mediation_outcome_referred'), filter_referral_org('med_ref_social_welfare')])
        ])
    )

    resolution_referral_ngo = SimpleCalculator(
        date_provider=date_reported_provided_mediated,
        filter=ORFilter([
            ANDFilter([filter_action('immediate_referral'), filter_immediate_referral_org('ngo')]),
            ANDFilter([filter_outcome('mediation_outcome_referred'), filter_referral_org('med_ref_ngo')])
        ])
    )

    resolution_referral_other = SimpleCalculator(
        date_provider=date_reported_provided_mediated,
        filter=ORFilter([
            ANDFilter([filter_action('immediate_referral'), filter_immediate_referral_org('referral_other')]),
            ANDFilter([filter_outcome('mediation_outcome_referred'), filter_referral_org('med_ref_other')])
        ])
    )

    resolution_other = SimpleCalculator(
        date_provider=date_reported_provided_mediated,
        filter=ORFilter([
            filter_action('actions_other'),
            filter_outcome('other_mediation_outcome', REPORT_INCIDENT_XMLNS),
            filter_outcome('other', FOLLOWUP_FORM_XMLNS)
        ]),
    )

    resolution_total = xcalc.or_calc([
        resolution_resolved_at_cvsu,
        resolution_referred_ta,
        resolution_referral_ta_court,
        resolution_referral_police,
        resolution_referral_social_welfare,
        resolution_referral_ngo,
        resolution_referral_other,
        resolution_unresolved,
        resolution_other],
        date_provider=date_reported_provided_mediated,
    )

    # ---------------------------------------------------------------------
    # services
    # ---------------------------------------------------------------------

    service_referral = SimpleCalculator(
        date_provider=date_reported_mediated,
        filter=ORFilter([
            filter_action('immediate_referral'),
            filter_service('referral_hostpital'),
            filter_outcome('mediation_outcome_referred')
        ])
    )

    service_mediation = SimpleCalculator(
        date_provider=date_reported,
        filter=ORFilter([filter_action('mediation_scheduled'), filter_action('mediation_provided')])
    )

    service_counselling = SimpleCalculator(
        date_provider=date_reported,
        filter=ORFilter([filter_service('counselling'), filter_service('couselling')])
    )

    service_psychosocial_support = SimpleCalculator(
        date_provider=date_reported,
        filter=filter_service('psychosocial_support')
    )

    service_first_aid = SimpleCalculator(
        date_provider=date_reported,
        filter=filter_service('first_aid')
    )

    service_shelter = SimpleCalculator(
        date_provider=date_reported,
        filter=filter_service('shelter')
    )

    service_other = SimpleCalculator(
        date_provider=date_reported,
        filter=ORFilter([filter_action('actions_other'), filter_service('services_other')])
    )

    service_total = xcalc.or_calc([
        service_referral,
        service_mediation,
        service_counselling,
        service_psychosocial_support,
        service_first_aid,
        service_shelter,
        service_other],
        date_provider=date_reported_mediated,
    )

    # ---------------------------------------------------------------------
    # outreach
    # ---------------------------------------------------------------------

    incidents = SimpleCalculator(
        date_provider=date_reported,
        filter=xcalc.FormPropertyFilter(xmlns=REPORT_INCIDENT_XMLNS)
    )

    outreach = SimpleCalculator(
        date_provider=lambda form: form.form.get('date', form.received_on),
        filter=xcalc.FormPropertyFilter(xmlns=OUTREACH_FORM_XMLNS)
    )

    iga = SimpleCalculator(
        date_provider=lambda form: form.form.get('start_date', form.received_on),
        filter=xcalc.FormPropertyFilter(xmlns=IGA_FORM_XMLNS)
    )

    # ---------------------------------------------------------------------
    # abuse
    # ---------------------------------------------------------------------

    abuse_children_in_household = SimpleCalculator(
        date_provider=date_reported,
        filter=xcalc.FormPropertyFilter(xmlns=REPORT_INCIDENT_XMLNS),
        indicator_calculator=IntegerPropertyReference(
            'form/nr_children_in_household', transform=lambda x: 0 if x == 999 else x)  # unknown value = 999
    )

    abuse_children_abused = SimpleCalculator(
        date_provider=date_reported,
        filter=xcalc.FormPropertyFilter(xmlns=REPORT_INCIDENT_XMLNS),
        indicator_calculator=IntegerPropertyReference(
            'form/no_children_abused', transform=lambda x: 0 if x == 999 else x)  # unknown value = 999
    )

    abuse_category_physical = SimpleCalculator(
        date_provider=date_reported,
        filter=filter_abuse('physical')
    )

    abuse_category_sexual = SimpleCalculator(
        date_provider=date_reported,
        filter=filter_abuse('sexual')
    )

    abuse_category_psychological = SimpleCalculator(
        date_provider=date_reported,
        filter=filter_abuse('psychological')
    )

    abuse_category_exploitation = SimpleCalculator(
        date_provider=date_reported,
        filter=filter_abuse('exploitation')
    )

    abuse_category_neglect = SimpleCalculator(
        date_provider=date_reported,
        filter=filter_abuse('neglect')
    )

    abuse_category_other = SimpleCalculator(
        date_provider=date_reported,
        filter=filter_abuse('abuse_other')
    )

    abuse_category_total = xcalc.or_calc([
        abuse_category_physical,
        abuse_category_sexual,
        abuse_category_psychological,
        abuse_category_exploitation,
        abuse_category_neglect,
        abuse_category_other],
        date_provider=date_reported
    )

    class Meta:
        app_label = 'cvsu'


def case_date_reported(case):
    return case.date_reported


def filter_case_outcome(outcome):
    return ccalc.CasePropertyFilter(
        type='victim',
        property_name='mediation_outcome',
        property_value=outcome
    )

UnicefMalawiFluffPillow = UnicefMalawiFluff.pillow()
