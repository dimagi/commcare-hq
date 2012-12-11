import logging
import calendar
import copy
from couchdbkit.ext.django.schema import Document, StringProperty, IntegerProperty, ListProperty
from couchdbkit.schema.base import DocumentSchema
import datetime
from couchdbkit.schema.properties import LazyDict
import numpy
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan, add_months, months_between
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.modules import to_function

class DocumentNotInDomainError(Exception):
    pass

class DocumentMismatchError(Exception):
    pass


class IndicatorDefinition(Document):
    """
        An Indicator Definition defines how to compute the indicator that lives
        in the namespaced computed_ property of a case or form.
    """
    namespace = StringProperty()
    domain = StringProperty()
    slug = StringProperty()
    version = IntegerProperty()
    class_path = StringProperty()

    _class_path = "corehq.apps.indicators.models"
    _returns_multiple = False

    def __init__(self, _d=None, **kwargs):
        super(IndicatorDefinition, self).__init__(_d, **kwargs)
        self.class_path = self._class_path

    def __str__(self):
        return "%s %s in namespace %s." % (self.__class__.__name__, self.slug, self.namespace)

    @classmethod
    def key_properties(cls):
        """
            The ordering of these property names should match the ordering of what's emitted in the first part of
            the couch views used for fetching these indicators. These views currently are:
            - indicators/dynamic_indicator_definitions (Couch View Indicator Defs)
            - indicators/indicator_definitions (Form and Case Indicator Defs)
        """
        return ["namespace", "domain", "slug"]

    @classmethod
    def indicator_list_view(cls):
        return "indicators/indicator_definitions"

    @classmethod
    def _generate_couch_key(cls, version=None, reverse=False, **kwargs):
        key = list()
        key_prefix = list()
        for p in cls.key_properties():
            k = kwargs.get(p)
            if k is not None:
                key_prefix.append(p)
                key.append(k)
        key = [" ".join(key_prefix)] + key
        couch_key = dict(startkey=key, endkey=key+[{}]) if version is None else dict(key=key+[version])
        if reverse:
            return dict(startkey=couch_key.get('endkey'), endkey=couch_key.get('startkey'))
        return couch_key

    @classmethod
    def update_or_create_unique(cls, namespace, domain, slug=None, version=None, **kwargs):
        """
            key_options should be formatted as an option list:
            [(key, val), ...]
        """
        couch_key = cls._generate_couch_key(
            version=version,
            namespace=namespace,
            domain=domain,
            slug=slug,
            **kwargs
        )
        unique_indicator = cls.view(cls.indicator_list_view(),
            reduce=False,
            include_docs=True,
            **couch_key
        ).first()
        if not unique_indicator:
            unique_indicator = cls(
                version=version,
                namespace=namespace,
                domain=domain,
                slug=slug,
                **kwargs
            )
        else:
            unique_indicator.namespace = namespace
            unique_indicator.domain = domain
            unique_indicator.slug = slug
            unique_indicator.version = version
            for key, val in kwargs.items():
                setattr(unique_indicator, key, val)
        return unique_indicator

    @classmethod
    def get_current(cls, namespace, domain, slug, version=None, wrap=True, **kwargs):

        couch_key = cls._generate_couch_key(
            namespace=namespace,
            domain=domain,
            slug=slug,
            version=version,
            reverse=True,
            **kwargs
        )
        doc = get_db().view(cls.indicator_list_view(),
            reduce=False,
            include_docs=False,
            descending=True,
            **couch_key
        ).first()

        if wrap:
            try:
                doc_class = to_function(doc.get('value', "%s.%s" % (cls._class_path, cls.__name__)))
                return doc_class.get(doc.get('id'))
            except Exception as e:
                logging.error("Could not fetch indicator: %s" % e)
                return None
        return doc

    @classmethod
    def all_slugs(cls, namespace, domain, **kwargs):
        couch_key = cls._generate_couch_key(
            namespace=namespace,
            domain=domain,
            reverse=True,
            **kwargs
        )
        couch_key['startkey'][0] = couch_key.get('startkey', [])[0]+' slug'
        couch_key['endkey'][0] = couch_key.get('endkey', [])[0]+' slug'
        data = cls.view(cls.indicator_list_view(),
            group=True,
            group_level=cls.key_properties().index('slug')+2,
            descending=True,
            **couch_key
        ).all()
        return [item.get('key',[])[-1] for item in data]

    @classmethod
    def get_all(cls, namespace, domain, version=None, **kwargs):
        all_slugs = cls.all_slugs(namespace, domain, **kwargs)
        all_indicators = list()
        for slug in all_slugs:
            indicator = cls.get_current(namespace, domain, slug, version=version, **kwargs)
            if indicator:
                all_indicators.append(indicator)
        return all_indicators


class DynamicIndicatorDefinition(IndicatorDefinition):
    description = StringProperty()
    title = StringProperty()
    base_doc = "DynamicIndicatorDefinition"

    @classmethod
    def indicator_list_view(cls):
        return "indicators/dynamic_indicator_definitions"

    @property
    def date_display_format(self):
        return "%b. %Y"

    def get_first_day_of_month(self, year, month):
        return datetime.datetime(year, month, 1,
            hour=0, minute=0, second=0, microsecond=0)

    def get_last_day_of_month(self, year, month):
        last_day = calendar.monthrange(year, month)[1]
        return datetime.datetime(year, month, last_day,
            hour=23, minute=59, second=59, microsecond=999999)

    def get_month_datespan(self, start, end=None):
        """
            start and end are (year, month) tuples
        """
        if end is None:
            end=start
        return DateSpan(
            self.get_first_day_of_month(start[0], start[1]),
            self.get_last_day_of_month(end[0], end[1]),
            format="%b %Y",
            inclusive=False
        )

    def get_first_days(self, current_month, num_previous_months, as_datespans=False):
        enddate = current_month or datetime.datetime.utcnow()
        enddate = self.get_first_day_of_month(enddate.year, enddate.month)
        (start_year, start_month) = add_months(enddate.year, enddate.month, -num_previous_months)
        startdate = self.get_last_day_of_month(start_year, start_month)

        months = months_between(startdate, enddate)

        month_dates = list()
        for year, month in months:
            if as_datespans:
                month_dates.append(self.get_month_datespan((year, month)))
            else:
                month_dates.append(self.get_first_day_of_month(year, month))

        datespan = self.get_month_datespan(
            (startdate.year, startdate.month),
            (enddate.year, enddate.month)
        )
        return month_dates, datespan

    def get_monthly_retrospective(self, user_ids=None, current_month=None, num_previous_months=12):
        raise NotImplementedError

    def get_value(self, user_ids, datespan=None):
        raise NotImplementedError


class CouchIndicatorDef(DynamicIndicatorDefinition):
    """
        This indicator defintion expects that it will deal with a couch view and an indicator key.
        If a user_id is provided when fetching the results, this definition will use:
        ["user", <domain_name>, <user_id>, <indicator_key>] as the main couch view key
        Otherwise it will use:
        ["all", <domain_name>, <indicator_key>]

    """
    couch_view = StringProperty()
    indicator_key = StringProperty()
    startdate_shift = IntegerProperty(default=0)
    enddate_shift = IntegerProperty(default=0)
    fixed_datespan_days = IntegerProperty(default=0)
    fixed_datespan_months = IntegerProperty(default=0)

    @property
    @memoized
    def group_results_in_retrospective(self):
        """
            Determines whether or not to group results in the retrospective
        """
        return any(getattr(self, field) for field in ('startdate_shift', 'enddate_shift',
                                                      'fixed_datespan_days', 'fixed_datespan_months'))

    def _get_results_key(self, user_id=None):
        prefix = "user" if user_id else "all"
        key = [prefix, self.domain]
        if user_id:
            key.append(user_id)
        key.append(self.indicator_key)
        return key

    def _apply_datespan_shifts(self, datespan):
        if datespan and not isinstance(datespan, DateSpan):
            raise ValueError("datespan must be an instance of DateSpan")

        if datespan:
            datespan = copy.copy(datespan)
            if self.fixed_datespan_days:
                datespan.startdate = datespan.enddate - datetime.timedelta(days=self.fixed_datespan_days)
            if self.fixed_datespan_months:
                start_year, start_month = add_months(datespan.enddate.year, datespan.enddate.month,
                    -self.fixed_datespan_months)
                try:
                    datespan.startdate = datetime.datetime(start_year, start_month, datespan.enddate.day,
                        datespan.enddate.hour, datespan.enddate.minute, datespan.enddate.second,
                        datespan.enddate.microsecond)
                except ValueError:
                    # day is out of range for month
                    datespan.startdate = self.get_last_day_of_month(start_year, start_month)

            datespan.startdate = datespan.startdate + datetime.timedelta(days=self.startdate_shift)
            datespan.enddate = datespan.enddate + datetime.timedelta(days=self.enddate_shift)

        return datespan

    def get_results_with_key(self, key, user_id=None, datespan=None, date_group_level=None, reduce=False):
        view_kwargs = dict()
        if datespan:
            view_kwargs.update(
                startkey=key+datespan.startdate_key_utc,
                endkey=key+datespan.enddate_key_utc+[{}]
            )
        else:
            view_kwargs.update(
                startkey=key,
                endkey=key+[{}]
            )
        if date_group_level:
            base_level = 5 if user_id else 4
            view_kwargs.update(
                group=True,
                group_level=base_level+date_group_level
            )
        else:
            view_kwargs.update(
                reduce=reduce
            )
        return get_db().view(self.couch_view,
            **view_kwargs
        ).all()

    def get_raw_results(self, user_ids, datespan=False, date_group_level=False, reduce=False):
        """
            date_group_level can be 0 to group by year, 1 to group by month and 2 to group by day
        """
        datespan = self._apply_datespan_shifts(datespan)
        results = []
        for user_id in user_ids:
            key = self._get_results_key(user_id)
            results.extend(self.get_results_with_key(key, user_id, datespan, date_group_level, reduce))
        return results

    def get_value(self, user_ids, datespan=None):
        value = 0
        results = self.get_raw_results(user_ids, datespan, reduce=True)
        for result in results:
            value += self._get_value_from_result(result)
        return value

    def _get_value_from_result(self, result):
        value = 0
        if isinstance(result, dict) or isinstance(result, LazyDict):
            result = [result]
        for item in result:
            new_val = item.get('value')
            if isinstance(new_val, dict) or isinstance(new_val, LazyDict):
                if '_total_unique' in new_val:
                    value += new_val.get('_total_unique', 0)
                elif '_sum_unique':
                    value += new_val.get('_sum_unique', 0)
            else:
                value += new_val
        return value

    def get_values_by_month(self, user_ids, datespan=None):
        totals = dict()
        result = self.get_raw_results(user_ids, datespan, date_group_level=1)
        for item in result:
            key = item.get('key', [])
            if len(key) >= 2:
                value = self._get_value_from_result(item)
                year = str(key[-2])
                month = str(key[-1])
                if not (month and year):
                    continue
                if year not in totals:
                    totals[year] = dict()
                if month not in totals[year]:
                    totals[year][month] = 0
                totals[year][month] += value
        return totals

    def get_values_by_year(self, user_ids, datespan=None):
        totals = dict()
        result = self.get_raw_results(user_ids, datespan, date_group_level=0)
        for item in result:
            key = item.get('key', [])
            value = self._get_value_from_result(item)
            if len(key) >= 1:
                year = str(key[-1])
                if not year:
                    continue
                if year not in totals:
                    totals[year] = 0
                totals[year] += value
        return totals

    def get_monthly_retrospective(self, user_ids=None, current_month=None, num_previous_months=12):
        if not isinstance(user_ids, list):
            user_ids = [user_ids]
        retro_months, datespan = self.get_first_days(current_month, num_previous_months,
            as_datespans=self.group_results_in_retrospective)
        monthly_totals = {} if self.group_results_in_retrospective else self.get_values_by_month(user_ids, datespan)
        retrospective = list()
        for i, this_month in enumerate(retro_months):
            startdate = this_month.startdate if self.group_results_in_retrospective else this_month
            y = str(startdate.year)
            m = str(startdate.month)
            if self.group_results_in_retrospective:
                month_value = self.get_value(user_ids, this_month)
            else:
                month_value = monthly_totals.get(y, {}).get(m, 0)
            retrospective.append(dict(
                date=startdate,
                value=month_value
            ))
        return retrospective

class NoGroupCouchIndicatorDefBase(CouchIndicatorDef):
    """
        Use this base for all CouchViewIndicatorDefinitions that have views which are not simply
        counted during the monthly retrospective.
    """

    @property
    def group_results_in_retrospective(self):
        return True

    def get_value(self, user_ids, datespan=None):
        raise NotImplementedError("You must override the parent's get_value. "
                                  "Reduce / group will not work here.")


class CountUniqueCouchIndicatorDef(NoGroupCouchIndicatorDefBase):
    """
        Use this indicator to count the # of unique emitted values.
    """

    def get_value(self, user_ids, datespan=None):
        results = self.get_raw_results(user_ids, datespan)
        all_emitted_values = [r['value'] for r in results]
        all_emitted_values = set(all_emitted_values)
        return len(all_emitted_values)


class MedianCouchIndicatorDef(NoGroupCouchIndicatorDefBase):
    """
        Get the median value of what is emitted. Assumes that emits are numbers.
    """

    def get_value(self, user_ids, datespan=None):
        results = self.get_raw_results(user_ids, datespan)
        values = [item.get('value', 0) for item in results if item.get('value')]
        return numpy.median(values) if values else 0


class SumLastEmittedCouchIndicatorDef(NoGroupCouchIndicatorDefBase):
    """
        Expects an emitted value formatted like:
        {
            _id: "<unique id string>",
            value: <number>,
        }
        It then finds the sum of all the last emitted unique values.
    """

    def get_value(self, user_ids, datespan=None):
        results = self.get_raw_results(user_ids, datespan)
        unique_values = {}
        for item in results:
            if item.get('value'):
                unique_values[item['value']['_id']] = item['value']['value']
        return sum(unique_values.values())


class CombinedCouchViewIndicatorDefinition(DynamicIndicatorDefinition):
    numerator_slug = StringProperty()
    denominator_slug = StringProperty()

    @property
    @memoized
    def numerator(self):
        return self.get_current(self.namespace, self.domain, self.numerator_slug)

    @property
    @memoized
    def denominator(self):
        return self.get_current(self.namespace, self.domain, self.denominator_slug)

    def get_value(self, user_ids, datespan=None):
        numerator = self.numerator.get_value(user_ids, datespan)
        denominator = self.denominator.get_value(user_ids, datespan)
        ratio = float(numerator)/float(denominator) if denominator > 0 else None
        return dict(
            numerator=numerator,
            denominator=denominator,
            ratio=ratio
        )

    def get_monthly_retrospective(self, user_ids=None, current_month=None, num_previous_months=12):
        numerator_retro = self.numerator.get_monthly_retrospective(user_ids, current_month, num_previous_months)
        denominator_retro = self.denominator.get_monthly_retrospective(user_ids, current_month, num_previous_months)
        combined_retro = list()
        for i, denominator in enumerate(denominator_retro):
            numerator = numerator_retro[i]
            n_val = numerator.get('value', 0)
            d_val = denominator.get('value', 0)
            ratio = float(n_val)/float(d_val) if d_val else None
            combined_retro.append(dict(
                date=denominator.get('date'),
                numerator=n_val,
                denominator=d_val,
                ratio=ratio
            ))
        return combined_retro


class DocumentIndicatorDefinition(IndicatorDefinition):
    """
        This IndicatorDefinition expects to get a value from a couchdbkit Document and then
        save that value in the computed_ property of that Document.

        So far, the types of Documents that support this are XFormInstance and CommCareCase
    """

    def get_clean_value(self, doc):
        """
            Add validation to whatever comes in as doc here...
        """
        if self.domain and doc.domain != self.domain:
            raise DocumentNotInDomainError
        return self.get_value(doc)

    def get_value(self, doc):
        raise NotImplementedError

    def get_existing_value(self, doc):
        try:
            return doc.computed_.get(self.namespace, {}).get(self.slug, {}).get('value')
        except AttributeError:
            return None


class FormDataIndicatorDefinitionMixin(DocumentSchema):
    """
        Use this mixin whenever you plan on dealing with forms in indicator definitions.
    """
    xmlns = StringProperty()

    def get_from_form(self, form_data, question_id):
        """
            question_id must be formatted like: path.to.question_id
        """
        if isinstance(question_id, basestring):
            question_id = question_id.split('.')
        if len(question_id) > 0 and form_data:
            return self.get_from_form(form_data.get(question_id[0]), question_id[1:])
        if (isinstance(form_data, dict) or isinstance(form_data, LazyDict)) and form_data.get('#text'):
            return form_data.get('#text')
        return form_data


class FormIndicatorDefinition(DocumentIndicatorDefinition, FormDataIndicatorDefinitionMixin):
    """
        This Indicator Definition defines an indicator that will live in the computed_ property of an XFormInstance
        document. The 'doc' passed through get_value and get_clean_value should be an XFormInstance.
    """
    base_doc = "FormIndicatorDefinition"

    def get_clean_value(self, doc):
        if not isinstance(doc, XFormInstance):
            raise ValueError("The document provided must be an instance of XFormInstance.")
        if not doc.xmlns == self.xmlns:
            raise DocumentMismatchError("The xmlns of the form provided does not match the one for this definition.")
        return super(FormIndicatorDefinition, self).get_clean_value(doc)

    @classmethod
    def key_properties(cls):
        return ["namespace", "domain", "xmlns", "slug"]


class FormDataAliasIndicatorDefinition(FormIndicatorDefinition):
    """
        This Indicator Definition is targeted for the scenarios where you have an indicator report across multiple
        domains and each domain's application doesn't necessarily have standardized question IDs. This provides a way
        of aliasing question_ids on a per-domain basis so that you can reference the same data in a standardized way
        as a computed_ indicator.
    """
    question_id = StringProperty()

    def get_value(self, doc):
        form_data = doc.get_form
        return self.get_from_form(form_data, self.question_id)


class CaseDataInFormIndicatorDefinition(FormIndicatorDefinition):
    """
        Use this indicator when you want to pull the value from a case property of a case related to a form
        and include it as an indicator for that form.
        This currently assumes the pre-2.0 model of CommCareCases and that there is only one related case per form.
        This should probably get rewritten to handle forms that update more than one type of case or for sub-cases.
    """
    case_property = StringProperty()

    def get_value(self, doc):
        form_data = doc.get_form
        related_case_id = form_data.get('case', {}).get('@case_id')
        if related_case_id:
            case = CommCareCase.get(related_case_id)
            if isinstance(case, CommCareCase) and hasattr(case, str(self.case_property)):
                return getattr(case, str(self.case_property))
        return None


class CaseIndicatorDefinition(DocumentIndicatorDefinition):
    """
        This Indicator Definition defines an indicator that will live in the computed_ property of a CommCareCase
        document. The 'doc' passed through get_value and get_clean_value should be a CommCareCase.
    """
    case_type = StringProperty()
    base_doc = "CaseIndicatorDefinition"

    def get_clean_value(self, doc):
        if not isinstance(doc, CommCareCase):
            raise ValueError("The document provided must be an instance of CommCareCase.")
        if not doc.type == self.case_type:
            raise DocumentMismatchError("The case provided should be a '%s' type case." % self.case_type)
        return super(CaseIndicatorDefinition, self).get_clean_value(doc)

    @classmethod
    def key_properties(cls):
        return ["namespace", "domain", "case_type", "slug"]


class FormDataInCaseIndicatorDefinition(CaseIndicatorDefinition, FormDataIndicatorDefinitionMixin):
    """
        Use this for when you want to grab all forms with the relevant xmlns in a case's xform_ids property and
        include a property from those forms as an indicator for this case.
    """
    question_id = StringProperty()
    _returns_multiple = True

    def get_related_forms(self, case):
        if not isinstance(case, CommCareCase):
            raise ValueError("case is not an instance of CommCareCase.")
        all_forms = case.get_forms()
        all_forms.reverse()
        related_forms = list()
        for form in all_forms:
            if form.xmlns == self.xmlns:
                related_forms.append(form)
        return related_forms

    def get_value(self, doc):
        existing_value = self.get_existing_value(doc)
        if not (isinstance(existing_value, dict) or isinstance(existing_value, LazyDict)):
            existing_value = dict()
        forms = self.get_related_forms(doc)
        for form in forms:
            if isinstance(form, XFormInstance):
                form_data = form.get_form
                existing_value[form.get_id] = dict(
                    value=self.get_from_form(form_data, self.question_id),
                    timeEnd=self.get_from_form(form_data, 'meta.timeEnd'),
                    received_on=form.received_on
                )
        return existing_value

