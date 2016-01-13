import datetime
from corehq.apps.change_feed import topics
from custom.bihar import getters, BIHAR_DOMAINS
from custom.bihar.calculations.homevisit import DateRangeFilter
from custom.bihar.calculations.utils import filters
from fluff.filters import Filter
from pillowtop.listener import BasicPillow
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
from custom.bihar.calculations import homevisit, pregnancy, postpartum, newborn, familyplanning, mortality
from custom.bihar.calculations.utils.visits import VISIT_TYPES
import fluff
from django.db import models

A_DAY = datetime.timedelta(days=1)

class BiharCase(CommCareCase):
    doc_type = 'CommCareCase'

    def dump_json(self):
        return {
            'case': self.to_json(),
            'forms': [f.to_json() for f in self.get_forms()]
        }

    @classmethod
    def from_dump(cls, json_dump):
        case = BiharCase.wrap(json_dump['case'])
        case._forms = [XFormInstance.wrap(f) for f in json_dump['forms']]
        case._forms_cache = dict((f._id, f) for f in case._forms)
        return case

    _forms = None
    _forms_cache = None
    def get_forms(self):
        if self._forms is None:
            self._forms = super(BiharCase, self).get_forms()
            self._forms_cache = dict((f._id, f) for f in self._forms)
        return self._forms

    class Meta:
        app_label = 'case'


class CareBiharFluff(fluff.IndicatorDocument):
    document_class = CommCareCase

    domains = BIHAR_DOMAINS
    group_by = ['domain', 'owner_id']

    kafka_topic = topics.CASE

    # home visit

    # home visit
    bp2 = homevisit.VisitCalculator(form_types=('bp', 'reg'),
            visit_type='bp',
            get_date_next=getters.date_next_bp,
            case_filter=lambda case: filters.relevant_predelivery_mother,
            additional_filter=DateRangeFilter(days=(94, 187)),
    )
    bp3 = homevisit.VisitCalculator(form_types=('bp', 'reg'),
            visit_type='bp',
            get_date_next=getters.date_next_bp,
            case_filter=lambda case: filters.relevant_predelivery_mother,
            additional_filter=DateRangeFilter(days=(0, 94)),
    )
    pnc = homevisit.VisitCalculator(
        form_types=['del', 'pnc', 'reg'],
        visit_type='pnc',
        get_date_next=getters.date_next_pnc,
        case_filter=filters.relevant_postdelivery_mother,
    )
    ebf = homevisit.VisitCalculator(
        form_types=['del', 'pnc', 'reg', 'eb'],
        visit_type='eb',
        get_date_next=getters.date_next_eb,
        case_filter=filters.relevant_postdelivery_mother,
    )
    cf = homevisit.VisitCalculator(
        form_types=['del', 'pnc', 'reg', 'eb', 'cf'],
        visit_type='cf',
        get_date_next=getters.date_next_cf,
        case_filter=filters.relevant_postdelivery_mother,
    )

    upcoming_deliveries = homevisit.DueNextMonth()
    deliveries = homevisit.RecentDeliveryList()
    new_pregnancies = homevisit.RecentlyOpened()
    no_bp_counseling = homevisit.NoBPList()
    no_ifa_tablets = homevisit.NoIFAList()
    no_emergency_prep = homevisit.NoEmergencyPrep()
    no_newborn_prep = homevisit.NoNewbornPrep()
    no_postpartum_counseling = homevisit.NoPostpartumCounseling()
    no_family_planning = homevisit.NoFamilyPlanning()

    # pregnancy

    hd = pregnancy.VisitedQuicklyBirthPlace(at='home')
    idv = pregnancy.VisitedQuicklyBirthPlace(at=('private', 'public'))
    idnb = pregnancy.BreastFedBirthPlace(at=('private', 'public'))
    born_at_home = pregnancy.LiveBirthPlace(at='home')
    born_at_public_hospital = pregnancy.LiveBirthPlace(at='public')
    born_in_transit = pregnancy.LiveBirthPlace(at='transit')
    born_in_private_hospital = pregnancy.LiveBirthPlace(at='private')

    # postpartum

    comp1 = postpartum.Complications(days=1)
    comp3 = postpartum.Complications(days=3)
    comp5 = postpartum.Complications(days=5)
    comp7 = postpartum.Complications(days=7)

    # newborn

    ptlb = newborn.PretermNewborn()
    lt2kglb = newborn.LessThan2Kilos()
    visited_weak_ones = newborn.VisitedWeakNewborn()
    skin_to_skin = newborn.NoSkinToSkin()
    feed_vigour = newborn.NotBreastfeedingVigorously()

    # family planning

    interested_in_fp = familyplanning.FamilyPlanning()
    adopted_fp = familyplanning.AdoptedFP()
    exp_int_fp = familyplanning.InterestInFP()
    no_fp = familyplanning.NoFP()
    pregnant_fp = familyplanning.PregnantInterestInFP()

    # mortality

    mother_mortality = mortality.MMCalculator()
    infant_mortality = mortality.IMCalculator()
    still_birth_public = mortality.StillBirthPlace(at='public')
    still_birth_home = mortality.StillBirthPlace(at='home')
    live_birth = mortality.LiveBirth()

    class Meta:
        app_label = 'bihar'

CareBiharFluffPillow = CareBiharFluff.pillow()


from .signals import *
