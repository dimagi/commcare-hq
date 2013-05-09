from couchdbkit.ext.django.schema import Document
from casexml.apps.case.models import CommCareCase
from bihar.calculations import home_visit
import fluff


class _(Document):
    pass


class CareBiharFluff(fluff.IndicatorDocument):
    document_class = CommCareCase

    domains = ('care-bihar',)
    group_by = ('domain', 'owner_id')


    # home visit

    bp2 = home_visit.BPCalculator(days=75, n_visits=2)
    bp3 = home_visit.BPCalculator(days=45, n_visits=3)
    pnc = home_visit.VisitCalculator(schedule=(1, 3, 6), visit_type='pnc')
    ebf = home_visit.VisitCalculator(
        schedule=(14, 28, 60, 90, 120, 150),
        visit_type='eb',
    )
    cf = home_visit.VisitCalculator(
        schedule=[m * 30 for m in (6, 7, 8, 9, 12, 15, 18)],
        visit_type='cf',
    )

    upcoming_deliveries = home_visit.UpcomingDeliveryList()
    deliveries = home_visit.RecentDeliveryList()
    no_bp_counseling = home_visit.NoBPList()
    new_pregnancies = home_visit.RecentRegistrationList()
    no_ifa_tablets = home_visit.NoIFAList()
    no_emergency_prep = home_visit.NoEmergencyPrep()
    no_newborn_prep = home_visit.NoNewbornPrep()
    no_postpartum_counseling = home_visit.NoPostpartumCounseling()
    no_family_planning = home_visit.NoFamilyPlanning()

    class Meta:
        app_label = 'bihar'

CareBiharFluffPillow = CareBiharFluff.pillow()