import fluff
from casexml.apps.case.models import CommCareCase
from corehq.fluff.calculators.case import CasePropertyFilter
from custom.care_pathways.utils import get_domain_configuration


def flat_field(fn):
    def getter(item):
        return unicode(fn(item) or "")
    return fluff.FlatField(getter)


# This calculator is necessary to generate 'date' field which is required in the database
class Numerator(fluff.Calculator):
    @fluff.null_emitter
    def numerator(self, case):
        yield None


class Property(fluff.Calculator):

    @fluff.date_emitter
    def value(self, case):
        config = get_domain_configuration(case.domain)['by_type_hierarchy']
        for chain in config:
            if chain['val'] == case['crop_id'].lower():
                for domain in chain['next']:
                    for practice in domain['next']:
                        ppt_prop = case.get_case_property(practice['val'])
                        yield {
                            'date': case.opened_on,
                            'value': 1 if ppt_prop == 'Y' else 0,
                            'group_by': [case.domain, chain['val'], domain['val'], practice['val']]
                        }


def get_property(case, property):
    configuration = get_domain_configuration(case.domain)
    if property in configuration['geography_hierarchy']:
        result = case.get_case_property(configuration['geography_hierarchy'][property]['prop'])
        return result.lower() if result else result
    return None


def get_mapping(case):
    value_chains = get_domain_configuration(case.domain)['by_type_hierarchy']
    return list({vc['val'] for vc in value_chains})


def get_domains_with_next(case):
    configuration = get_domain_configuration(case.domain)['by_type_hierarchy']
    domains = []
    for chain in configuration:
        domains.extend(chain['next'])
    return domains


def get_domains(case):
    domains = get_domains_with_next(case)
    return list({d['val'] for d in domains})


def get_practices(case):
    domains = get_domains_with_next(case)
    practices = []
    for domain in domains:
        practices.extend(domain['next'])
    return list({p['val'] for p in practices})

def get_gender(case):
    gender =case.get_case_property('farmer_gender')
    return '1' if gender and gender[0].lower() == 'f' else '0'


class GeographyFluff(fluff.IndicatorDocument):
    def case_property(property):
        return flat_field(lambda case: get_property(case, property))

    document_class = CommCareCase
    document_filter = CasePropertyFilter(type='farmer_record')
    domains = ('pathways-india-mis', 'pathways-tanzania',)
    group_by = ('domain',)

    save_direct_to_sql = True
    numerator = Numerator()
    lvl_1 = case_property('lvl_1')
    lvl_2 = case_property('lvl_2')
    lvl_3 = case_property('lvl_3')
    lvl_4 = case_property('lvl_4')
    lvl_5 = case_property("lvl_5")


class FarmerRecordFluff(fluff.IndicatorDocument):
    def case_property(property):
        return flat_field(lambda case: get_property(case, property))

    document_class = CommCareCase
    document_filter = CasePropertyFilter(type='farmer_record')
    domains = ('pathways-india-mis', 'pathways-tanzania',)
    group_by = ('domain',
                fluff.AttributeGetter('value_chain', lambda c: get_mapping(c)),
                fluff.AttributeGetter('domains', lambda c: get_domains(c)),
                fluff.AttributeGetter('practices', lambda c: get_practices(c)))

    save_direct_to_sql = True
    lvl_1 = case_property('lvl_1')
    lvl_2 = case_property('lvl_2')
    lvl_3 = case_property('lvl_3')
    lvl_4 = case_property('lvl_4')
    lvl_5 = case_property("lvl_5")
    group_id = flat_field(lambda c: c.get_case_property('group_id'))
    ppt_year = flat_field(lambda c: c.get_case_property('ppt_year'))
    owner_id = flat_field(lambda c: c.get_case_property('owner_id'))
    gender = flat_field(lambda c: get_gender(c))
    group_leadership = flat_field(lambda c: c.get_case_property('farmer_is_leader'))
    schedule = flat_field(lambda c: (c.get_case_property('farmer_social_category') or '').lower())
    prop = Property()



GeographyFluffPillow = GeographyFluff.pillow()
FarmerRecordFluffPillow = FarmerRecordFluff.pillow()