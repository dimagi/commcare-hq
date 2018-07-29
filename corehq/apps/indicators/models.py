from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import logging
import calendar
import copy
import dateutil
import numpy
import datetime
from dimagi.ext.couchdbkit import Document, DocumentSchema, StringProperty, IntegerProperty, DateTimeProperty
from casexml.apps.case.models import CommCareCase
from corehq.apps.crud.models import AdminCRUDDocumentMixin
from corehq.apps.indicators.admin.crud import (IndicatorAdminCRUDManager,
        FormAliasIndicatorAdminCRUDManager, FormLabelIndicatorAdminCRUDManager,
        CaseDataInFormIndicatorAdminCRUDManager, FormDataInCaseAdminCRUDManager, CouchIndicatorCRUDManager,
        BaseDynamicIndicatorCRUDManager, CombinedCouchIndicatorCRUDManager)
from couchforms.models import XFormInstance
from dimagi.utils.dates import DateSpan, add_months, months_between
from memoized import memoized
from dimagi.utils.modules import to_function
from dimagi.utils.couch.cache import cache_core
import six


class DocumentNotInDomainError(Exception):
    pass


class DocumentMismatchError(Exception):
    pass


class IndicatorDefinition(Document, AdminCRUDDocumentMixin):
    """
    An Indicator Definition defines how to compute the indicator that lives
    in the namespaced computed_ property of a case or form.
    """
    namespace = StringProperty()
    domain = StringProperty()
    slug = StringProperty()
    version = IntegerProperty()
    class_path = StringProperty()
    last_modified = DateTimeProperty()

    _admin_crud_class = IndicatorAdminCRUDManager

    _class_path = "corehq.apps.indicators.models"
    _returns_multiple = False

    def __init__(self, _d=None, **kwargs):
        super(IndicatorDefinition, self).__init__(_d, **kwargs)
        self.class_path = self._class_path

    def __str__(self):
        return "\n\n%(class_name)s - Modified %(last_modified)s\n %(slug)s, domain: %(domain)s," \
            " version: %(version)s, namespace: %(namespace)s. ID: %(indicator_id)s." % {
                'class_name': self.__class__.__name__,
                'slug': self.slug,
                'domain': self.domain,
                'version': self.version,
                'namespace': self.namespace,
                'last_modified': (self.last_modified.strftime('%m %B %Y at %H:%M')
                                  if self.last_modified else "Ages Ago"),
                'indicator_id': self._id,
            }

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
    def increment_or_create_unique(cls, namespace, domain, slug=None, version=None, **kwargs):
        """
        If an indicator with the same namespace, domain, and version exists, create a new indicator with the
        version number incremented.
        # todo, this feels a bit buggy, so replace bulk copy indicators with
        # copy to domain at some point
        """
        couch_key = cls._generate_couch_key(
            namespace=namespace,
            domain=domain,
            slug=slug,
            reverse=True,
            **kwargs
        )

        existing_indicator = cls.view(
            cls.indicator_list_view(),
            reduce=False,
            include_docs=True,
            descending=True,
            limit=1,
            **couch_key
        ).first()
        if existing_indicator:
            version = existing_indicator.version + 1
        elif version is None:
            version = 1

        new_indicator = cls(
            version=version,
            namespace=namespace,
            domain=domain,
            slug=slug,
            **kwargs
        )
        new_indicator.last_modified = datetime.datetime.utcnow()

        new_indicator.save()
        return new_indicator

    @classmethod
    def copy_to_domain(cls, domain, doc, override=False):
        """
        This copies an indicator doc to the current domain. Intended to be used
        by the export indicators feature.
        :param domain: the name of the domain the indicator should be copied to
        :param doc: the dictionary of kwargs to create the indicator
        :param override: Whether to override the existing indicator
        :return: True if indicator was copied, False if not
        """
        for reserved in ['_id', '_rev', 'last_modified']:
            if reserved in doc:
                del doc[reserved]

        couch_key = cls._generate_couch_key(
            domain=domain,
            reverse=True,
            **doc
        )
        existing_indicator = cls.view(
            cls.indicator_list_view(),
            reduce=False,
            include_docs=False,
            descending=True,
            limit=1,
            **couch_key
        ).first()
        if existing_indicator and not override:
            return False
        if existing_indicator:
            existing_indicator.delete()
        new_indicator = cls(domain=domain, **doc)
        new_indicator.last_modified = datetime.datetime.utcnow()
        new_indicator.save()
        return True

    @classmethod
    @memoized
    def get_current(cls, namespace, domain, slug, version=None, wrap=True, **kwargs):

        couch_key = cls._generate_couch_key(
            namespace=namespace,
            domain=domain,
            slug=slug,
            version=version,
            reverse=True,
            **kwargs
        )
        results = cache_core.cached_view(cls.get_db(), cls.indicator_list_view(),
            cache_expire=60*60*6,
            reduce=False,
            include_docs=False,
            descending=True,
            **couch_key
        )
        doc = results[0] if results else None
        if wrap and doc:
            try:
                doc_class = to_function(doc.get('value', "%s.%s" % (cls._class_path, cls.__name__)))
                doc_instance = doc_class.get(doc.get('id'))
                return doc_instance
            except Exception as e:
                logging.error("No matching documents found for indicator %s: %s" % (slug, e))
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
        return [item.get('key', [])[-1] for item in data]

    @classmethod
    @memoized
    def get_all(cls, namespace, domain, version=None, **kwargs):
        all_slugs = cls.all_slugs(namespace, domain, **kwargs)
        all_indicators = list()
        for slug in all_slugs:
            indicator = cls.get_current(namespace, domain, slug, version=version, **kwargs)
            if indicator and issubclass(indicator.__class__, cls):
                all_indicators.append(indicator)
        return all_indicators

    @classmethod
    def get_all_of_type(cls, namespace, domain, show_only_current=False):
        key = ["type", namespace, domain, cls.__name__]
        indicators = cls.view(
            cls.indicator_list_view(),
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key+[{}]
        ).all()
        unique = {}
        for ind in indicators:
            if ind.base_doc == "CaseIndicatorDefinition":
                specific_doc = ind.case_type
            elif ind.base_doc == "FormIndicatorDefinition":
                specific_doc = ind.xmlns
            else:
                specific_doc = "couch"
            unique["%s.%s.%s" % (ind.slug, ind.namespace, specific_doc)] = ind
        return list(unique.values())

    @classmethod
    def get_nice_name(cls):
        return "Indicator Definition"


class DynamicIndicatorDefinition(IndicatorDefinition):
    description = StringProperty()
    title = StringProperty()
    base_doc = "DynamicIndicatorDefinition"

    _admin_crud_class = BaseDynamicIndicatorCRUDManager

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
        if num_previous_months == 0:
            months = [(enddate.year, enddate.month)]

        month_dates = []
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

    def get_monthly_retrospective(self, user_ids=None, current_month=None,
                                  num_previous_months=12, return_only_dates=False,
                                  is_debug=False):
        """
        :param user_ids: List of CommCareUser Ids contributing to this indicator
        :param current_month: integer of the current month
        :param num_previous_months: number of months to be subtracted from the
        current month to get the full retrospective
        :param return_only_dates:
        :param is_debug: True if debugging the view
        :return: list of dictionaries with retrospective data
        """
        raise NotImplementedError

    def get_value(self, user_ids, datespan=None, is_debug=False):
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

    _admin_crud_class = CouchIndicatorCRUDManager

    @property
    @memoized
    def group_results_in_retrospective(self):
        """
            Determines whether or not to group results in the retrospective
        """
        return not any(getattr(self, field) for field in ('startdate_shift', 'enddate_shift',
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
            now = datetime.datetime.utcnow()

            # make sure we don't go over the current day
            # remember, there is no timezone support for this yet
            if datespan.enddate > now:
                datespan.enddate = now

            datespan.enddate = datespan.enddate.replace(hour=23, minute=59, second=59, microsecond=999999)
            if self.fixed_datespan_days:
                datespan.startdate = datespan.enddate - datetime.timedelta(days=self.fixed_datespan_days,
                                                                           microseconds=-1)
            if self.fixed_datespan_months:
                # By making the assumption that the end date is always the end of the month
                # the first months adjustment is accomplished by moving the start date to
                # the beginning of the month. Any additional months are subtracted in the usual way
                start = self.get_first_day_of_month(datespan.enddate.year, datespan.enddate.month)
                start_year, start_month = add_months(start.year, start.month, -(self.fixed_datespan_months - 1))
                datespan.startdate = start.replace(year=start_year, month=start_month)

            if self.startdate_shift:
                datespan.startdate = datespan.startdate + datetime.timedelta(days=self.startdate_shift)
            if self.enddate_shift:
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

        # Pull Data from the MVP-only DB
        from mvp_docs.models import IndicatorXForm
        db = IndicatorXForm.get_db()
        section = self.couch_view.split('/')
        couch_view = "%s_indicators/%s" % (section[0], section[1])

        return cache_core.cached_view(db, couch_view, cache_expire=60*60*6, **view_kwargs)

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

    def get_value(self, user_ids, datespan=None, is_debug=False):
        results = self.get_raw_results(user_ids, datespan, reduce=not is_debug)
        if is_debug:
            contributing_ids = [r['id'] for r in results]
            value = len(contributing_ids)
            return value, contributing_ids
        value = 0
        for result in results:
            value += self._get_value_from_result(result)
        return value

    def _get_value_from_result(self, result):
        value = 0
        if isinstance(result, dict):
            result = [result]
        for item in result:
            new_val = item.get('value')
            if isinstance(new_val, dict):
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

    def get_monthly_retrospective(self, user_ids=None, current_month=None,
                                  num_previous_months=12, return_only_dates=False,
                                  is_debug=False):
        if not isinstance(user_ids, list):
            user_ids = [user_ids]
        results_are_grouped = self.group_results_in_retrospective and not is_debug

        retro_months, datespan = self.get_first_days(current_month, num_previous_months,
            as_datespans=not results_are_grouped)
        monthly_totals = {}
        if results_are_grouped and not return_only_dates:
            monthly_totals = self.get_values_by_month(user_ids, datespan)

        retrospective = []
        for i, this_month in enumerate(retro_months):
            startdate = this_month if results_are_grouped else this_month.startdate
            y = str(startdate.year)
            m = str(startdate.month)
            if return_only_dates:
                month_value = 0
            elif results_are_grouped:
                month_value = monthly_totals.get(y, {}).get(m, 0)
            else:
                month_value = self.get_value(user_ids, this_month, is_debug=is_debug)
            monthly_result = {
                'date': startdate,
            }
            if isinstance(month_value, tuple):
                monthly_result['debug_data'] = month_value[1]
                month_value = month_value[0]
            monthly_result['value'] = month_value
            retrospective.append(monthly_result)
        return retrospective

    @classmethod
    def get_nice_name(cls):
        return "Simple Indicators"

    @classmethod
    def increment_or_create_unique(cls, namespace, domain,
                                   slug=None, version=None, **kwargs):
        if 'couch_view' in kwargs:
            # make sure that a viewname with trailing whitespace NEVER
            # gets created.
            kwargs['couch_view'] = kwargs['couch_view'].strip()

        super(CouchIndicatorDef, cls).increment_or_create_unique(
            namespace, domain, slug=slug, version=version, **kwargs
        )


class NoGroupCouchIndicatorDefBase(CouchIndicatorDef):
    """
        Use this base for all CouchViewIndicatorDefinitions that have views which are not simply
        counted during the monthly retrospective.
    """

    @property
    def group_results_in_retrospective(self):
        return False

    def get_value(self, user_ids, datespan=None, is_debug=False):
        raise NotImplementedError("You must override the parent's get_value. "
                                  "Reduce / group will not work here.")


class CountUniqueCouchIndicatorDef(NoGroupCouchIndicatorDefBase):
    """
        Use this indicator to count the # of unique emitted values.
    """

    def get_value(self, user_ids, datespan=None, is_debug=False):
        results = self.get_raw_results(user_ids, datespan)
        all_emitted_values = [r['value'] for r in results]
        all_emitted_values = set(all_emitted_values)
        value = len(all_emitted_values)
        return (value, list(all_emitted_values)) if is_debug else value

    @classmethod
    def get_nice_name(cls):
        return "Count Unique Emitted Values"


class MedianCouchIndicatorDef(NoGroupCouchIndicatorDefBase):
    """
        Get the median value of what is emitted. Assumes that emits are numbers.
    """

    def get_value(self, user_ids, datespan=None, is_debug=False):
        results = self.get_raw_results(user_ids, datespan)
        data = dict([(r['id'], r['value']) for r in results])
        value = numpy.median(list(data.values())) if list(data.values()) else None
        if is_debug:
            return value, data
        return value

    @classmethod
    def get_nice_name(cls):
        return "Median of Emitted Values"


class SumLastEmittedCouchIndicatorDef(NoGroupCouchIndicatorDefBase):
    """
        Expects an emitted value formatted like:
        {
            _id: "<unique id string>",
            value: <number>,
        }
        It then finds the sum of all the last emitted unique values.
    """

    def get_value(self, user_ids, datespan=None, is_debug=False):
        results = self.get_raw_results(user_ids, datespan)
        unique_values = {}
        for item in results:
            if item.get('value'):
                unique_values[item['value']['_id']] = item['value']['value']
        value = sum(unique_values.values())
        return (value, list(unique_values)) if is_debug else value

    @classmethod
    def get_nice_name(cls):
        return "Sum Last Emitted Unique Values"


class CombinedCouchViewIndicatorDefinition(DynamicIndicatorDefinition):
    numerator_slug = StringProperty()
    denominator_slug = StringProperty()

    _admin_crud_class = CombinedCouchIndicatorCRUDManager

    @property
    @memoized
    def numerator(self):
        return self.get_current(self.namespace, self.domain, self.numerator_slug)

    @property
    @memoized
    def denominator(self):
        return self.get_current(self.namespace, self.domain, self.denominator_slug)

    def get_value(self, user_ids, datespan=None, is_debug=False):
        numerator = self.numerator.get_value(user_ids, datespan, is_debug=is_debug)
        denominator = self.denominator.get_value(user_ids, datespan, is_debug=is_debug)

        debug_data = {}
        if isinstance(denominator, tuple):
            debug_data["denominator"] = denominator[1]
            denominator = denominator[0]
        if isinstance(numerator, tuple):
            debug_data["numerator"] = numerator[1]
            numerator = numerator[0]

        ratio = float(numerator) / float(denominator) if denominator > 0 else None
        value = {
            'numerator': numerator,
            'denominator': denominator,
            'ratio': ratio,
        }
        if is_debug:
            value['contributing_ids'] = debug_data
        return value

    def get_monthly_retrospective(self, user_ids=None, current_month=None,
                                  num_previous_months=12, return_only_dates=False,
                                  is_debug=False):
        numerator_retro = self.numerator.get_monthly_retrospective(
            user_ids, current_month, num_previous_months,
            return_only_dates, is_debug=is_debug)
        denominator_retro = self.denominator.get_monthly_retrospective(
            user_ids, current_month, num_previous_months,
            return_only_dates, is_debug=is_debug)
        combined_retro = []
        for i, denominator in enumerate(denominator_retro):
            numerator = numerator_retro[i]
            n_val = numerator.get('value', 0)
            d_val = denominator.get('value', 0)
            ratio = float(n_val) / float(d_val) if d_val else None

            monthly_combined = {
                'date': denominator.get('date'),
                'numerator': n_val,
                'denominator': d_val,
                'ratio': ratio,
            }

            if is_debug:
                monthly_combined.update({
                    'contributing_ids': {
                        'numerator': numerator.get('contributing_ids'),
                        'denominator': denominator.get('contributing_ids'),
                    },
                })

            combined_retro.append(monthly_combined)
        return combined_retro

    @classmethod
    def get_nice_name(cls):
        return "Combined Indicators (Ratio)"


class BaseDocumentIndicatorDefinition(IndicatorDefinition):
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

    def update_computed_namespace(self, computed, document):
        """
            Returns True if this document should be updated and saved with the new indicator definition.
        """
        update_computed = True
        existing_indicator = computed.get(self.slug)
        if isinstance(existing_indicator, dict):
            update_computed = existing_indicator.get('version') != self.version
        if update_computed:
            computed[self.slug] = self.get_doc_dict(document)
        return computed, update_computed

    def get_doc_dict(self, document):
        return {
            'version': self.version,
            'value': self.get_clean_value(document),
            'multi_value': self._returns_multiple,
            'type': self.doc_type,
            'updated': datetime.datetime.utcnow(),
        }


class FormDataIndicatorDefinitionMixin(DocumentSchema):
    """
        Use this mixin whenever you plan on dealing with forms in indicator definitions.
    """
    xmlns = StringProperty()

    def get_from_form(self, form_data, question_id):
        """
            question_id must be formatted like: path.to.question_id
        """
        if isinstance(question_id, six.string_types):
            question_id = question_id.split('.')
        if len(question_id) > 0 and form_data:
            return self.get_from_form(form_data.get(question_id[0]), question_id[1:])
        if isinstance(form_data, dict) and '#text' in form_data:
            return form_data['#text']
        return form_data


class FormIndicatorDefinition(BaseDocumentIndicatorDefinition, FormDataIndicatorDefinitionMixin):
    """
        This Indicator Definition defines an indicator that will live in the computed_ property of an XFormInstance
        document. The 'doc' passed through get_value and get_clean_value should be an XFormInstance.
    """
    base_doc = "FormIndicatorDefinition"

    def get_clean_value(self, doc):
        if not isinstance(doc, XFormInstance) or not issubclass(doc.__class__, XFormInstance):
            raise ValueError("The document provided must be an instance of XFormInstance.")
        if not doc.xmlns == self.xmlns:
            raise DocumentMismatchError("The xmlns of the form provided does not match the one for this definition.")
        return super(FormIndicatorDefinition, self).get_clean_value(doc)

    @classmethod
    def key_properties(cls):
        return ["namespace", "domain", "xmlns", "slug"]


class FormLabelIndicatorDefinition(FormIndicatorDefinition):
    """
    This indicator definition labels the forms of a certain XMLNS with the slug provided as its type.
    This type is used as a way to label that form in couch views.
    For example, I want an XMLNS of http://domain.commcarehq.org/child/visit/ to map to child_visit_form.
    """
    _admin_crud_class = FormLabelIndicatorAdminCRUDManager

    def get_value(self, doc):
        return self.slug

    @classmethod
    def get_label_for_xmlns(cls, namespace, domain, xmlns):
        key = [namespace, domain, xmlns]
        label = cls.get_db().view("indicators/form_labels",
                                   reduce=False,
                                   descending=True,
                                   limit=1,
                                   startkey=key + [{}],
                                   endkey=key
        ).one()
        return label['value'] if label else ""

    @classmethod
    def get_nice_name(cls):
        return "Form Label Indicators"


class FormDataAliasIndicatorDefinition(FormIndicatorDefinition):
    """
    This Indicator Definition is targeted for the scenarios where you have an indicator report across multiple
    domains and each domain's application doesn't necessarily have standardized question IDs. This provides a way
    of aliasing question_ids on a per-domain basis so that you can reference the same data in a standardized way
    as a computed_ indicator.
    """
    question_id = StringProperty()

    _admin_crud_class = FormAliasIndicatorAdminCRUDManager

    def get_value(self, doc):
        form_data = doc.form
        return self.get_from_form(form_data, self.question_id)

    @classmethod
    def get_nice_name(cls):
        return "Form Alias Indicators"


class CaseDataInFormIndicatorDefinition(FormIndicatorDefinition):
    """
    Use this indicator when you want to pull the value from a case property of a case related to a form
    and include it as an indicator for that form.
    This currently assumes the pre-2.0 model of CommCareCases and that there is only one related case per form.
    This should probably get rewritten to handle forms that update more than one type of case or for sub-cases.
    """
    case_property = StringProperty()

    _admin_crud_class = CaseDataInFormIndicatorAdminCRUDManager

    def get_value(self, doc):
        case = self._get_related_case(doc)
        if case is not None and hasattr(case, str(self.case_property)):
            return getattr(case, str(self.case_property))
        return None

    def _get_related_case(self, xform):
        form_data = xform.form
        related_case_id = form_data.get('case', {}).get('@case_id')
        if related_case_id:
            try:
                return CommCareCase.get(related_case_id)
            except Exception:
                pass
        return None

    def update_computed_namespace(self, computed, document):
        computed, is_update = super(CaseDataInFormIndicatorDefinition,
            self).update_computed_namespace(computed, document)
        if not is_update:
            # check to see if the related case has changed information
            case = self._get_related_case(document)
            if case is not None:
                try:
                    indicator_updated = computed.get(self.slug, {}).get('updated')
                    if indicator_updated and not isinstance(indicator_updated, datetime.datetime):
                        indicator_updated = dateutil.parser.parse(indicator_updated)
                    is_update = not indicator_updated or case.server_modified_on > indicator_updated
                    if is_update:
                        computed[self.slug] = self.get_doc_dict(document)
                except ValueError:
                    pass
        return computed, is_update

    @classmethod
    def get_nice_name(cls):
        return "Related Case Property Indicators"


class CaseIndicatorDefinition(BaseDocumentIndicatorDefinition):
    """
        This Indicator Definition defines an indicator that will live in the computed_ property of a CommCareCase
        document. The 'doc' passed through get_value and get_clean_value should be a CommCareCase.
    """
    case_type = StringProperty()
    base_doc = "CaseIndicatorDefinition"

    def get_clean_value(self, doc):
        if not isinstance(doc, CommCareCase) or not issubclass(doc.__class__, CommCareCase):
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

    _admin_crud_class = FormDataInCaseAdminCRUDManager

    def get_related_forms(self, case):
        if not isinstance(case, CommCareCase) or not issubclass(case.__class__, CommCareCase):
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
        if not isinstance(existing_value, dict):
            existing_value = dict()
        forms = self.get_related_forms(doc)
        for form in forms:
            if isinstance(form, XFormInstance) or not issubclass(doc.__class__, XFormInstance):
                form_data = form.form
                existing_value[form.get_id] = {
                    'value': self.get_from_form(form_data, self.question_id),
                    'timeEnd': self.get_from_form(form_data, 'meta.timeEnd'),
                    'received_on': form.received_on,
                }
        return existing_value

    def update_computed_namespace(self, computed, document):
        computed, is_update = super(FormDataInCaseIndicatorDefinition,
            self).update_computed_namespace(computed, document)

        if not is_update:
            # check to see if more relevant forms have been added to the case since the last time
            # this indicator was computed
            related_forms = self.get_related_forms(document)
            if related_forms:
                try:
                    value_list = computed.get(self.slug, {}).get('value', {})
                    saved_form_ids = list(value_list)
                    current_ids = set([f._id for f in related_forms])
                    is_update = len(current_ids.difference(saved_form_ids)) > 0
                    if is_update:
                        computed[self.slug] = self.get_doc_dict(document)
                except Exception as e:
                    logging.error("Error updating computed namespace for doc %s: %s" % (document._id, e))

        return computed, is_update

    @classmethod
    def get_nice_name(cls):
        return "Related Form Question ID Indicators"
