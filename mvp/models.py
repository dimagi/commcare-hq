from StringIO import StringIO
import datetime
import copy
from couchdbkit.ext.django.schema import IntegerProperty, BooleanProperty, StringProperty
import dateutil
import logging
import pytz
from corehq.apps.indicators.models import DynamicIndicatorDefinition, NoGroupCouchIndicatorDefBase
from dimagi.utils.couch.database import get_db

class MVP(object):
    NAMESPACE = "mvp_indicators"
    DOMAINS = ["mvp-potou", "mvp-sauri"]
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

    def get_value(self, user_ids, datespan=None):
        if datespan:
            enddate = datespan.enddate_utc
        else:
            enddate = datetime.datetime.utcnow()
        days = []
        for user_id in user_ids:
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
                days.append(td.days)
            except Exception:
                pass
        if len(days) == 1:
            return days[0]
        if not days:
            return None
        return days


class MVPActiveCasesIndicatorDefinition(NoGroupCouchIndicatorDefBase):
    """
        Returns # active cases.
    """
    _class_path = CLASS_PATH
    case_type = StringProperty()

    def _get_cases_by_status(self, status, user_id, datespan):
        datespan = self._apply_datespan_shifts(datespan)
        key_prefix = [status]
        if self.indicator_key:
            key_prefix.append(self.indicator_key)
        key = self._get_results_key(user_id=user_id)
        if self.case_type:
            key = key[0:2] + [self.case_type] + key[2:]
        key[-1] = " ".join(key_prefix)
        datespan_by_status = self._format_datespan_by_case_status(datespan, status)
        return self.get_results_with_key(key, user_id=user_id, datespan=datespan_by_status)

    def get_value_by_status(self, status, user_id, datespan):
        cases = self._get_cases_by_status(status, user_id, datespan)
        return [r['id'] for r in cases]

    def get_value(self, user_ids, datespan=None):
        open_cases = []
        closed_on_closed_cases = []
        opened_on_closed_cases = []
        for user_id in user_ids:
            open_cases.extend(self.get_value_by_status("opened_on open", user_id, datespan))
            closed_on_closed_cases.extend(self.get_value_by_status("closed_on closed", user_id, datespan))
            opened_on_closed_cases.extend(self.get_value_by_status("opened_on closed", user_id, datespan))

        open_ids = set(open_cases)
        closed_on_closed_ids = set(closed_on_closed_cases)
        opened_on_closed_ids = set(opened_on_closed_cases)

        closed_ids = closed_on_closed_ids.intersection(opened_on_closed_ids)

        all_cases = open_ids.union(closed_ids)
        return len(all_cases)

    def _format_datespan_by_case_status(self, datespan, status):
        datespan = copy.copy(datespan) # copy datespan
        if status == 'opened_on open':
            datespan.startdate = None
        elif status == 'closed_on closed':
            datespan.enddate = None
        elif status == 'opened_on closed':
            datespan.startdate = None
        return datespan


class MVPChildCasesByAgeIndicatorDefinition(MVPActiveCasesIndicatorDefinition):
    """
        Returns the number of child cases that were active within the datespan provided and have a date of birth
        that is less than the age provided by days in age.
    """
    max_age_in_days = IntegerProperty()
    min_age_in_days = IntegerProperty(default=0)
    show_active_only = BooleanProperty(default=True)
    is_dob_in_datespan = BooleanProperty(default=False)

    def get_value_by_status(self, status, user_id, datespan):
        cases = self._get_cases_by_status(status, user_id, datespan)
        return self._filter_by_age(cases, datespan)

    def _filter_by_age(self, results, datespan):
        valid_case_ids = []
        for item in results:
            if item.get('value'):
                try:
                    date_of_birth = dateutil.parser.parse(item['value'])
                    valid_id = False
                    if self.is_dob_in_datespan:
                        if datespan.startdate <= date_of_birth <= datespan.enddate:
                            valid_id = True
                    else:
                        td = datespan.enddate - date_of_birth
                        if self.min_age_in_days <= td.days < self.max_age_in_days:
                            valid_id = True
                    if valid_id:
                        valid_case_ids.append(item['id'])
                except Exception as e:
                    logging.error("date of birth could not be parsed")
        return valid_case_ids

    def get_value(self, user_ids, datespan=None):
        if self.show_active_only:
            return super(MVPChildCasesByAgeIndicatorDefinition, self).get_value(user_ids, datespan=datespan)
        else:
            results = self.get_raw_results(user_ids, datespan)
            all_cases = self._filter_by_age(results, datespan)
        return len(all_cases)
