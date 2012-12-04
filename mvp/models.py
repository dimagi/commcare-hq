import datetime
from couchdbkit.ext.django.schema import IntegerProperty, BooleanProperty
import dateutil
import pytz
from corehq.apps.indicators.models import DynamicIndicatorDefinition, ActiveCasesCouchViewIndicatorDefinition
from dimagi.utils.couch.database import get_db

class MVP(object):
    NAMESPACE = "mvp_indicators"
    # todo: add mvp-sauri back in here
    DOMAINS = ["mvp-potou"]
    VISIT_FORMS = dict(
        pregnancy_visit='http://openrosa.org/formdesigner/185A7E63-0ECD-4D9A-8357-6FD770B6F065',
        child_visit='http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A',
        household_visit='http://openrosa.org/formdesigner/266AD1A0-9EAE-483E-B4B2-4E85D6CA8D4B'
    )
    REGISTRATION_FORMS = dict(
        child_registration='http://openrosa.org/formdesigner/E6511C2B-DFC8-4DEA-8200-CC2F2CED00DA',
    )
    CLOSE_FORMS = dict(
        pregnancy_close="http://openrosa.org/formdesigner/01EB3014-71CE-4EBE-AE34-647EF70A55DE",
        child_close="http://openrosa.org/formdesigner/AC164B28-AECA-45C9-B7F6-E0668D5AF84B",
        death_without_registration="http://openrosa.org/formdesigner/b3af1fddeb661ee045fef1e764995440ea8f057f",
    )

CLASS_PATH = "mvp.models"


class MVPDaysSinceLastTransmission(DynamicIndicatorDefinition):
    _class_path = CLASS_PATH

    def get_value(self, user_id=None, datespan=None):
        if datespan:
            enddate = datespan.enddate_utc
        else:
            enddate = datetime.datetime.utcnow()
        couch_view = "reports/submit_history" if user_id else "reports/all_submissions"
        key = [self.domain]
        if user_id:
            key.append(user_id)
        results = get_db().view(couch_view,
            reduce=False,
            include_docs=False,
            descending=True,
            startkey=key+[enddate.isoformat(),{}],
            endkey=key
        ).first()
        try:
            last_transmission = results['key'][-1]
            last_date = dateutil.parser.parse(last_transmission)
            last_date = last_date.replace(tzinfo=pytz.utc)
            enddate = enddate.replace(tzinfo=pytz.utc)
            td = enddate - last_date
            return td.days
        except Exception:
            pass
        return None


class MVPChildCasesByAgeIndicatorDefinition(ActiveCasesCouchViewIndicatorDefinition):
    """
        Returns the number of child cases that were active within the datespan provided and have a date of birth
        that is less than the age provided by days in age.
    """
    _class_path = CLASS_PATH
    age_in_days = IntegerProperty()
    filter_by_active = BooleanProperty(default=True)

    def _get_cases_by_status(self, status, user_id, datespan):
        results = super(MVPChildCasesByAgeIndicatorDefinition, self)._get_cases_by_status(status, user_id, datespan)
        return self._filter_by_age(results, datespan)

    def _filter_by_age(self, results, datespan):
        valid_case_ids = []
        for item in results:
            if item.get('value'):
                try:
                    date_of_birth = dateutil.parser.parse(item['value'])
                    td = datespan.enddate - date_of_birth
                    if td.days < self.age_in_days:
                        valid_case_ids.append(item['id'])
                except Exception as e:
                    log.error("date of birth could not be parsed")
        return set(valid_case_ids)


    def get_value(self, user_id=None, datespan=None):
        if self.filter_by_active:
            opened_on_cases = self._get_cases_by_status("opened_on", user_id, datespan)
            closed_on_cases = self._get_cases_by_status("closed_on", user_id, datespan)
            all_cases = opened_on_cases.union(closed_on_cases)
        else:
            results = self.get_couch_results(user_id, datespan)
            all_cases = self._filter_by_age(results, datespan)
        return len(all_cases)
