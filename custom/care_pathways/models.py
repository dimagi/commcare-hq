import fluff
from casexml.apps.case.models import CommCareCase
from corehq.fluff.calculators.case import CasePropertyFilter
from custom.care_pathways.utils import get_domain_configuration
from custom.opm.opm_reports.models import flat_field

# This calculator is necessary to generate 'date' field which is required in the database
class Numerator(fluff.Calculator):
    @fluff.null_emitter
    def numerator(self, case):
        yield None

def get_property(case, property):
    configuration = get_domain_configuration(case.domain)
    if property in configuration:
        result = case.get_case_property(configuration[property])
        return result.lower() if result else result
    return None

class GeographyFluff(fluff.IndicatorDocument):
    def case_property(property):
        return flat_field(lambda case: get_property(case, property))

    document_class = CommCareCase
    document_filter = CasePropertyFilter(type= 'farmer_record')
    domains = ('pathways-india-mis','pathways-tanzania',)
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
    document_filter = CasePropertyFilter(type= 'farmer_record')
    domains = ('pathways-india-mis','pathways-tanzania',)
    group_by = ('domain',)

    save_direct_to_sql = True
    numerator = Numerator()
    lvl_1 = case_property('group_name')
    lvl_2 = case_property('farmer_gender')
    lvl_3 = case_property('lvl_3')
    lvl_4 = case_property('lvl_4')
    lvl_5 = case_property("lvl_5")

GeographyFluffPillow = GeographyFluff.pillow()
FarmerRecordFluffPillow = FarmerRecordFluff.pillow()
