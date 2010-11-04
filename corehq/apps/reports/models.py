from couchdbkit.ext.django.schema import *
from corehq.util.mixins import UnicodeMixIn


class CPregnancy(Document, UnicodeMixIn):
    """
    Document representing a pregnancy in couchdb
    """
    patient_id = StringProperty(required=True)
    clinic_id = StringProperty(required=True) # we assume one clinic per pregnancy
    id = StringProperty(required=True)
    lmp = DateProperty(required=True)
    edd = DateProperty(required=True)
    visits = IntegerProperty(required=True)
    first_visit_date = DateProperty(required=True)
    
    # report values
    hiv_test_done = BooleanProperty()
    ever_tested_positive = BooleanProperty()
    got_nvp_when_tested_positive = BooleanProperty()
    got_azt = BooleanProperty()
    got_azt_on_consecutive_visits = BooleanProperty()
    rpr_given_on_first_visit = BooleanProperty()
    tested_positive_rpr = BooleanProperty()
    got_penicillin_when_rpr_positive = BooleanProperty()
    partner_got_penicillin_when_rpr_positive = BooleanProperty()
    got_three_doses_fansidar = BooleanProperty()
    dates_danger_signs_followed = ListProperty()
    dates_danger_signs_not_followed = ListProperty()
    dates_preeclamp_treated = ListProperty()
    dates_preeclamp_not_treated = ListProperty()
    
    def __unicode__(self):
        return "%s, Pregnancy: %s (due: %s)" % (self.patient_id, self.id, self.edd)
    
    
import corehq.apps.reports.signals