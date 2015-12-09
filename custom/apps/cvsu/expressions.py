import functools
from couchdbkit.ext.django.schema import StringProperty
from corehq.apps.groups.models import Group
from corehq.apps.userreports.specs import TypeProperty
from custom.apps.cvsu.filters import ALL_CVSU_GROUP
from custom.apps.cvsu.utils import REPORT_INCIDENT_XMLNS, FOLLOWUP_FORM_XMLNS, \
    OUTREACH_FORM_XMLNS, IGA_FORM_XMLNS, CVSUFilters
from dimagi.ext.jsonobject import JsonObject


def get_group_id(item):
    user_id = item['form']['meta']['userID']
    if not user_id:
        return
    groups = Group.by_user(user_id, wrap=False)
    for g in groups:
        if g != ALL_CVSU_GROUP:
            return g


def check_clause(item, function):
    f = CVSUFilters(item)
    if function(f):
        return 1


def resolution_resolved_at_cvsu(f):
    return (
        (f.filter_action('mediation_provided') and f.filter_outcome('resolved', REPORT_INCIDENT_XMLNS)) or
        f.filter_outcome('resolved', FOLLOWUP_FORM_XMLNS)
    )


def resolution_unresolved(f):
    return (
        (f.filter_action('mediation_provided') and f.filter_outcome('unresolved', REPORT_INCIDENT_XMLNS)) or
        f.filter_outcome('unresolved', FOLLOWUP_FORM_XMLNS)
    )


def resolution_case_withdrawn(f):
    return (
        f.filter_action('mediation_provided') and f.filter_outcome('case_withdrawn', REPORT_INCIDENT_XMLNS) or
        f.filter_outcome('case_withdrawn', FOLLOWUP_FORM_XMLNS)
    )


def _referral(f, first_key, second_key):
    return (
        (
            (f.filter_action('immediate_referral') and f.filter_immediate_referral_org(first_key)) or
            (f.filter_outcome('mediation_outcome_referred') and f.filter_referral_org(second_key))
        )
    )


def resolution_referred_ta(f):
    return _referral(f, 'ta', 'ta')


def resolution_referral_ta_court(f):
    return _referral(f, 'ta_court', 'ta_court')


def resolution_referral_police(f):
    return _referral(f, 'police', 'med_ref_police')


def resolution_referral_social_welfare(f):
    return _referral(f, 'social_welfare', 'med_ref_social_welfare')


def resolution_referral_ngo(f):
    return _referral(f, 'ngo', 'med_ref_ngo')


def resolution_referral_other(f):
    return _referral(f, 'referral_other', 'med_ref_other')


def resolution_other(f):
    return (
        f.filter_action('actions_other') or f.filter_outcome('other_mediation_outcome', REPORT_INCIDENT_XMLNS) or
        f.filter_outcome('other', FOLLOWUP_FORM_XMLNS)
    )


def resolution(f):
    return any([
        resolution_resolved_at_cvsu(f),
        resolution_referred_ta(f),
        resolution_referral_ta_court(f),
        resolution_referral_police(f),
        resolution_referral_social_welfare(f),
        resolution_referral_ngo(f),
        resolution_referral_other(f),
        resolution_unresolved(f),
        resolution_other(f)
    ])


def service_referral(f):
    return (
        f.filter_action('immediate_referral') or f.filter_service('referral_hostpital')
        or f.filter_outcome('mediation_outcome_referred')
    )


def service_mediation(f):
    return f.filter_action('mediation_scheduled') or f.filter_action('mediation_provided')


def service_counselling(f):
    return f.filter_service('counselling') or f.filter_service('couselling')


def service_psychosocial_support(f):
    return f.filter_service('psychosocial_support')


def service_first_aid(f):
    return f.filter_service('first_aid')


def service_shelter(f):
    return f.filter_service('shelter')


def service_other(f):
    return f.filter_action('actions_other') or f.filter_service('services_other')


def service_total(f):
    return any([
        service_referral(f),
        service_mediation(f),
        service_counselling(f),
        service_psychosocial_support(f),
        service_first_aid(f),
        service_shelter(f),
        service_other(f)]
    )


def incidents(f):
    return f.xmlns == REPORT_INCIDENT_XMLNS


def outreach(f):
    return f.xmlns == OUTREACH_FORM_XMLNS


def iga(f):
    return f.xmlns == IGA_FORM_XMLNS


def abuse_category_physical(f):
    return f.filter_abuse('physical')


def abuse_category_sexual(f):
    return f.filter_abuse('sexual')


def abuse_category_psychological(f):
    return f.filter_abuse('psychological')


def abuse_category_exploitation(f):
    return f.filter_abuse('exploitation')


def abuse_category_neglect(f):
    return f.filter_abuse('neglect')


def abuse_category_other(f):
    return f.filter_abuse('abuse_other')


def abuse_category_total(f):
    return any([
        abuse_category_physical(f),
        abuse_category_sexual(f),
        abuse_category_psychological(f),
        abuse_category_exploitation(f),
        abuse_category_neglect(f),
        abuse_category_other(f)
    ])


def abuse_transform(item, property_name):
    f = CVSUFilters(item)
    if f.xmlns == REPORT_INCIDENT_XMLNS:
        if property_name not in item['form'] or not item['form'][property_name]:
            return
        value = int(item['form'][property_name])
        return 0 if value == 999 else value


def date_reported(item):
    return item['form'].get('date_reported', item['received_on'])


def date_provided(item):
    return item['form'].get('mediation_provided_date', item['received_on'])


def date_mediated(item):
    date = item['form'].get('mediation_date', item['received_on'])
    return date or item['received_on']  # some forms empty strings


def date_reported_mediated(item):
    xmlns = item['xmlns']
    if xmlns == FOLLOWUP_FORM_XMLNS:
        return date_mediated(item)
    else:
        return date_reported(item)


def date_reported_provided_mediated(item):
    f = CVSUFilters(item)
    if f.xmlns == FOLLOWUP_FORM_XMLNS:
        return date_mediated(item)
    elif f.filter_action('immediate_referral') or f.filter_action('actions_other'):
        return date_reported(item)
    else:
        return date_provided(item)


class ExpressionsFactory(object):
    @staticmethod
    def get_expression_function(name):
        if name == 'group_id':
            return get_group_id

        if name == 'abuse_children_in_household':
            return functools.partial(abuse_transform, property_name='nr_children_in_household')

        if name == 'abuse_children_abused':
            return functools.partial(abuse_transform, property_name='no_children_abused')

        if name == 'date_reported_mediated':
            return date_reported_mediated

        if name == 'date_reported_provided_mediated':
            return date_reported_provided_mediated

        return functools.partial(check_clause, function={
            'resolution_resolved_at_cvsu': resolution_resolved_at_cvsu,
            'resolution_unresolved': resolution_unresolved,
            'resolution_case_withdrawn': resolution_case_withdrawn,
            'resolution_referred_ta': resolution_referred_ta,
            'resolution_referral_ta_court': resolution_referral_ta_court,
            'resolution_referral_police': resolution_referral_police,
            'resolution_referral_social_welfare': resolution_referral_social_welfare,
            'resolution_referral_ngo': resolution_referral_ngo,
            'resolution_referral_other': resolution_referral_other,
            'resolution_other': resolution_other,
            'resolution': resolution,
            'service_referral': service_referral,
            'service_mediation': service_mediation,
            'service_counselling': service_counselling,
            'service_psychosocial_support': service_psychosocial_support,
            'service_first_aid': service_first_aid,
            'service_shelter': service_shelter,
            'service_other': service_other,
            'service_total': service_total,
            'incidents': incidents,
            'outreach': outreach,
            'iga': iga,
            'abuse_category_physical': abuse_category_physical,
            'abuse_category_sexual': abuse_category_sexual,
            'abuse_category_psychological': abuse_category_psychological,
            'abuse_category_exploitation': abuse_category_exploitation,
            'abuse_category_neglect': abuse_category_neglect,
            'abuse_category_other': abuse_category_other,
            'abuse_category_total': abuse_category_total
        }[name])


class CVSUExpressionSpec(JsonObject):
    type = TypeProperty('cvsu_expression')
    name = StringProperty()

    def __call__(self, item, context=None):
        return (ExpressionsFactory.get_expression_function(self.name))(item)


def cvsu_expression(spec, context):
    wrapped = CVSUExpressionSpec.wrap(spec)
    return wrapped
