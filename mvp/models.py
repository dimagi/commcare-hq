from couchdbkit.ext.django.schema import StringProperty, IntegerProperty, ListProperty, SetProperty, DocumentSchema, Document
import datetime
from couchdbkit.schema.properties import LazyDict
import dateutil
from django.utils.safestring import mark_safe
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import CaseIndicatorDefinition, FormDataInCaseIndicatorDefinition,\
    PopulateRelatedCasesWithIndicatorDefinitionMixin, CaseDataInFormIndicatorDefinition, CouchViewIndicatorDefinition
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan

class MVP(object):
    NAMESPACE = "mvp_indicators"
    DOMAINS = ["mvp-sauri", "mvp-potou"]
    VISIT_FORMS = dict(
        pregnancy_visit='http://openrosa.org/formdesigner/185A7E63-0ECD-4D9A-8357-6FD770B6F065',
        child_visit='http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A',
        household_visit='http://openrosa.org/formdesigner/266AD1A0-9EAE-483E-B4B2-4E85D6CA8D4B'
    )

CLASS_PATH = "mvp.models"

class MVPCannotFetchCaseError(Exception):
    pass


class MVPRelatedCaseMixin(DocumentSchema):
    related_case_type = StringProperty()

    def get_related_cases(self, original_case):
        if hasattr(original_case, 'household_head_health_id'):
            household_id = original_case.household_head_health_id
        elif hasattr(original_case, 'household_head_id'):
            household_id = original_case.household_head_id
        else:
            raise MVPCannotFetchCaseError("Cannot fetch appropriate case from %s." % original_case.get_id)
        key = [original_case.domain, self.related_case_type, household_id]
        cases = CommCareCase.view("mvp/cases_by_household",
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key+[{}]
        ).all()
        return cases


class MVPRelatedCaseDataInFormIndicatorDefinition(CaseDataInFormIndicatorDefinition, MVPRelatedCaseMixin):
    _class_path = CLASS_PATH
    _returns_multiple = True

    def get_value(self, doc):
        values = list()
        form_data = doc.get_form
        related_case_id = form_data.get('case', {}).get('@case_id')
        if related_case_id:
            case = CommCareCase.get(related_case_id)
            if isinstance(case, CommCareCase):
                related_cases = self.get_related_cases(case)
                for rc in related_cases:
                    if hasattr(rc, str(self.case_property)):
                        values.append(dict(
                            case_id=rc.get_id,
                            case_opened=rc.opened_on,
                            case_closed=rc.closed_on,
                            value=getattr(rc, str(self.case_property))
                        ))
        return values


class MVPRelatedCaseDataInCaseIndicatorDefinition(CaseIndicatorDefinition, MVPRelatedCaseMixin):
    related_case_property = StringProperty()

    _class_path = CLASS_PATH
    _returns_multiple = True

    def get_value(self, case):
        values = list()
        related_cases = self.get_related_cases(case)
        for rc in related_cases:
            if hasattr(rc, str(self.related_case_property)):
                values.append(dict(
                    case_id=rc.get_id,
                    case_opened=rc.opened_on,
                    case_closed=rc.closed_on,
                    value=getattr(rc, str(self.related_case_property))
                ))
        return values


class MVPUniqueEmitDateSpan(DateSpan):
    date_group_level = None

    def _format_key_by_level(self, key):
        if key and self.date_group_level is not None:
            return [self.date_group_level] + key[0:self.date_group_level]
        return key

    @property
    def startdate_key_utc(self):
        return self._format_key_by_level(super(MVPUniqueEmitDateSpan, self).startdate_key_utc)

    @property
    def enddate_key_utc(self):
        return self._format_key_by_level(super(MVPUniqueEmitDateSpan, self).enddate_key_utc)


class MVPCouchViewIndicatorDefinition(CouchViewIndicatorDefinition):
    _class_path = CLASS_PATH


class MVPActiveCasesCouchViewIndicatorDefinition(MVPCouchViewIndicatorDefinition):
    """
        THIS IS REALLY REALLY UGLY. I'm so sorry. I did my best with the time I had.
        Cheers,
        --Biyeun
    """

    def _format_datespan_by_status(self, datespan, date_status):
        common_kwargs = dict(
            format=datespan.format,
            inclusive=datespan.inclusive,
            timezone=datespan.timezone
        )
        if date_status == 'opened_on':
            datespan = DateSpan(
                None,
                datespan.enddate,
                **common_kwargs
            )
        elif date_status == "closed_on":
            datespan = DateSpan(
                None,
                datespan.startdate,
                **common_kwargs
            )
        return datespan

    def _get_cases(self, case_status, date_status,
                   user_id=None, datespan=None):
        full_indicator = [case_status, self.indicator_key]
        key = self._get_results_key(user_id)
        key[-1] = " ".join(full_indicator).strip()
        key.append(date_status)

        results = self._get_results_with_key(key, user_id, self._format_datespan_by_status(datespan, date_status))

        return set([item.get('key',[])[-1] for item in results]), results

    def _get_valid_case_ids(self, closed_opened_on_ids, closed_closed_on_ids, open_opened_on_ids):
        valid_closed_cases = closed_opened_on_ids.difference(closed_closed_on_ids)
        valid_cases = open_opened_on_ids.union(valid_closed_cases)
        return valid_cases

    def _get_valid_cases_and_results(self, closed_opened_on, closed_closed_on, open_opened_on):
        valid_cases = self._get_valid_case_ids(closed_opened_on[0], closed_closed_on[0], open_opened_on[0])
        all_results = closed_opened_on[1] + closed_closed_on[1] + open_opened_on[1]
        valid_results = list()
        for result in all_results:
            case_id = result.get('key', [])[-1]
            if case_id in valid_cases:
                valid_results.append(result)
        return valid_cases, valid_results

    def get_couch_results(self, user_id=None, datespan=None, date_group_level=None, reduce=False):
        if date_group_level:
            raise ValueError("Sorry, but date_group_level is not supported for this indicator.")
        if reduce:
            raise ValueError("Sorry, but reduce is not supported for this indicator")

        datespan = self._apply_datespan_shifts(datespan)
        common_kwargs = dict(
            user_id=user_id,
            datespan=datespan
        )

        # Closed Cases Opened Before the End Date
        closed_opened_on = self._get_cases("closed", "opened_on", **common_kwargs)

        # Closed Cases Opened Before the Start Date
        closed_closed_on = self._get_cases("closed", "closed_on", **common_kwargs)

        # Open Cases Opened Before the End Date
        open_opened_on = self._get_cases("open", "opened_on", **common_kwargs)

        valid_cases, valid_results = self._get_valid_cases_and_results(
            closed_opened_on,
            closed_closed_on,
            open_opened_on
        )

        return len(valid_cases)

    def get_totals(self, user_id=None, datespan=None):
        return self.get_couch_results(user_id, datespan)
