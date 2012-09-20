import logging
from couchdbkit.ext.django.schema import Document, StringProperty, IntegerProperty, ListProperty, BooleanProperty, DateTimeProperty
from couchdbkit.schema.base import DocumentSchema
import datetime
from couchdbkit.schema.properties import LazyDict
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.modules import to_function

OPERATOR_CHOICES = [('<','Less Than'), ('<=','Less Than or Equal To'),
    ('>', 'Greater Than'), ('=>','Greater Than or Equal To'),
    ('==','Equal To'), ('!=', 'Not Equal To'),
    ('in','Contains'), ('not in', 'Does Not Contain')]

class DocumentNotInDomainError(Exception):
    pass


class IndicatorBase(Document):
    domain = StringProperty()
    slug = StringProperty()
    version = IntegerProperty()
    class_path = StringProperty()

    _class_path = "corehq.apps.indicators.models"

    def __init__(self, _d=None, **kwargs):
        super(IndicatorBase, self).__init__(_d, **kwargs)
        self.class_path = self._class_path

    @classmethod
    def get_current(cls, **kwargs):
        raise NotImplementedError

    @classmethod
    def all_slugs(cls, **kwargs):
        raise NotImplementedError

    @classmethod
    def get_all(cls, **kwargs):
        all_slugs = cls.all_slugs(**kwargs)
        all_indicators = list()
        for slug in all_slugs:
            doc = cls.get_current(include_docs=False, slug=slug, **kwargs)
            try:
                doc_class = to_function(doc.get('value', "%s.%s" % (cls._class_path, cls.__name__)))
                all_indicators.append(doc_class.get(doc.get('id')))
            except Exception as e:
                print "Error", e
        return all_indicators


class Indicator(IndicatorBase):
    topic = StringProperty()
    description = StringProperty()

    base_doc = 'Indicator'

    def get_value(self, **kwargs):
        return NotImplemented

    @classmethod
    def get_or_create_by_domain_slug_version(cls, domain, slug, version):
        indicator = cls.get_by_domain_slug_version(domain, slug, version)
        if not indicator:
            indicator = cls(domain=domain, slug=slug, version=version)
            indicator.save()
        return indicator

    @classmethod
    def get_by_domain_slug_version(cls, domain, slug, version):
        return cls.view('indicators/all_indicators',
            reduce=False,
            include_docs=True,
            key=["all", domain, slug, version]
        ).first()

    @classmethod
    def get_current(cls, **kwargs):
        domain = kwargs.get('domain')
        slug = kwargs.get('slug')
        version = kwargs.get('version')
        include_docs = kwargs.get('include_docs', True)

        startkey_suffix = [version] if version else [{}]
        key=["all", domain, slug]
        return cls.view('indicators/all_indicators',
            reduce=False,
            include_docs=include_docs,
            startkey=key+startkey_suffix,
            endkey=key,
            descending=True
        ).first()

    @classmethod
    def all_slugs(cls, **kwargs):
        domain = kwargs.get('domain')
        type = kwargs.get('type', 'all')

        key = [type, domain]
        data = cls.view("indicators/all_indicators",
            group=True,
            group_level=2,
            descending=True,
            startkey=key+[{}],
            endkey=key
        ).all()
        return [item.get('key',[])[-1] for item in data]


class HistoricalIndicator(Indicator):
    original_indicator_id = StringProperty()
    computed_for_date = DateTimeProperty()
    computed_on_date = DateTimeProperty()
    is_numeric = BooleanProperty(default=False)
    computed_value = StringProperty()

    def get_value(self, **kwargs):
        return float(self.computed_value) if self.is_numeric else self.computed_value


class ReducedCouchViewIndicator(Indicator):
    """
        Assumes that the couch view is keyed by the domain.
        Start and end dates are appended to the last part of the key.
    """
    couch_view = StringProperty()
    key_prefix = ListProperty()
    key_suffix = ListProperty()
    is_numeric = BooleanProperty(default=True)

    def get_value(self, **kwargs):
        default_value = 0 if self.is_numeric else None

        startdate = kwargs.get('startdate')
        enddate = kwargs.get('enddate')
        startkey_suffix = [startdate] if startdate else []
        endkey_suffix = [enddate] if enddate else [{}]
        key = self.key_prefix + [self.domain] + self.key_suffix

        data = get_db().view(self.couch_view,
            reduce=True,
            startkey=key+startkey_suffix,
            endkey=key+endkey_suffix
        ).first()

        if not data:
            return default_value

        return data.get('value', default_value)


class ProportionalIndicator(Indicator):
    """
        numerator and denominator are path.to.IndicatorClass strings.
    """
    numerator = StringProperty()
    denominator = StringProperty()

    @property
    def value(self, **kwargs):
        try:
            numerator = to_function(self.numerator).get_current(self.domain, self.slug, self.version)
            denominator = to_function(self.denominator).get_current(self.domain, self.slug, self.version)
            return numerator.get_value(**kwargs)/denominator.get_value(**kwargs)
        except ZeroDivisionError:
            pass
        except Exception as e:
            logging.error("Could not compute %s with id %s due to error: %s" %
                (self.__class__.__name__, self.get_id, e)
            )
        return 0


class IndicatorDefinition(IndicatorBase):
    """
        An Indicator Definition lives in the namespaced computed_ property of a
        case or form. It's purpose is to provide additional parameters that are computed
        on form submission or case modification. These properties can then be used in
        the full Indicator calculation.
    """
    namespace = StringProperty()

    _returns_multiple = False

    def __str__(self):
        return "%s %s in namespace %s." % (self.__class__.__name__, self.slug, self.namespace)

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

    @classmethod
    def key_params_order(cls):
        return ["namespace", "domain", "slug"]

    @classmethod
    def couch_view(cls):
        return "indicators/indicator_definitions"

    @classmethod
    def update_or_create_unique(cls, **kwargs):
        """
            key_options should be formatted as an option list:
            [(key, val), ...]
        """
        key = list()
        key_prefix = list()
        version = kwargs.get('version')

        for p in cls.key_params_order():
            k = kwargs.get(p)
            if k is not None:
                key_prefix.append(p)
                key.append(k)

        key = [" ".join(key_prefix)] + key
        query_options = dict(startkey=key, endkey=key+[{}]) if version is None else dict(key=key+[version])
        unique_indicator = cls.view(cls.couch_view(),
            reduce=False,
            include_docs=True,
            **query_options
        ).first()
        if not unique_indicator:
            unique_indicator = cls(**kwargs)
        else:
            for key, val in kwargs.items():
                setattr(unique_indicator, key, val)
        return unique_indicator

    @classmethod
    def get_current(cls, **kwargs):
        namespace = kwargs.get('namespace')
        domain = kwargs.get('domain')
        slug = kwargs.get('slug')
        version = kwargs.get('version')
        include_docs = kwargs.get('include_docs', True)

        startkey_suffix = [version] if version else [{}]
        key=["namespace domain slug", namespace, domain, slug]
        return cls.view('indicators/indicator_definitions',
            reduce=False,
            include_docs=include_docs,
            startkey=key+startkey_suffix,
            endkey=key,
            descending=True
        ).first()

    @classmethod
    def all_slugs(cls, **kwargs):
        namespace = kwargs.get('namespace')
        domain = kwargs.get('domain')
        key = [" ".join(cls.key_params_order()), namespace, domain]
        data = cls.view("indicators/indicator_definitions",
            group=True,
            group_level=len(cls.key_params_order())+1,
            descending=True,
            startkey=key+[{}],
            endkey=key
        ).all()
        return [item.get('key',[])[-1] for item in data]


class FormDataIndicatorDefinitionMixin(DocumentSchema):
    xmlns = StringProperty()

    def get_from_form(self, form_data, prop_ref):
        if len(prop_ref) > 0 and form_data:
            return self.get_from_form(form_data.get(prop_ref[0]), prop_ref[1:])
        result = form_data.get('#text') if form_data and ('#text' in form_data) else form_data
        return result


class FormIndicatorDefinition(IndicatorDefinition, FormDataIndicatorDefinitionMixin):
    base_doc = "FormIndicatorDefinition"

    def get_clean_value(self, doc):
        if not isinstance(doc, XFormInstance):
            raise ValueError("The document provided must be an instance of XFormInstance.")
        if not doc.xmlns == self.xmlns:
            raise ValueError("The xmlns of the form provided does not match the one for this definition.")
        return super(FormIndicatorDefinition, self).get_clean_value(doc)

    @classmethod
    def key_params_order(cls):
        return ["namespace", "domain", "xmlns", "slug"]


class CaseIndicatorDefinition(IndicatorDefinition):
    case_type = StringProperty()
    base_doc = "CaseIndicatorDefinition"

    def get_clean_value(self, doc):
        if not isinstance(doc, CommCareCase):
            raise ValueError("The document provided must be an instance of CommCareCase.")
        if not doc.type == self.case_type:
            raise ValueError("The case provided should be a 'child' type case.")
        return super(CaseIndicatorDefinition, self).get_clean_value(doc)

    @classmethod
    def key_params_order(cls):
        return ["namespace", "domain", "case_type", "slug"]


class FormDataInCaseIndicatorDefinition(CaseIndicatorDefinition, FormDataIndicatorDefinitionMixin):
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
            print "existing value is of type", type(existing_value)
            existing_value = dict()
        forms = self.get_related_forms(doc)
        for form in forms:
            if isinstance(form, XFormInstance):
                form_data = form.get_form
                existing_value[form.get_id] = dict(
                    value=self.get_value_for_form(form_data),
                    timeEnd=form_data.get('meta', {}).get('timeEnd'),
                    received_on=form.received_on
                )
        return existing_value

    def get_value_for_form(self, form_data):
        raise NotImplementedError


class BooleanIndicatorDefinitionMixin(DocumentSchema):
    compared_property = StringProperty()
    expression = StringProperty() # example: '%(value)s' not in 'foo bar'

    _compared_property_value = None
    def evaluate_expression(self):
        print self.expression % dict(value=self._compared_property_value)
        try:
            return eval(self.expression % dict(value=self._compared_property_value))
        except Exception:
            return False


class BooleanFormIndicatorDefinition(FormIndicatorDefinition, BooleanIndicatorDefinitionMixin):
    """
        Evaluate boolean expression from a form property.
    """
    def get_value(self, doc):
        try:
            self._compared_property_value = self.get_from_form(doc.get_form,
                self.compared_property.split('.'))
            return self.evaluate_expression()
        except Exception:
            return False


class BooleanCaseIndicatorDefinition(CaseIndicatorDefinition, BooleanIndicatorDefinitionMixin):
    """
        Evaluate boolean expression referencing a case property.
    """
    def get_value(self, doc):
        if not hasattr(doc, str(self.compared_property)):
            return False
        self._compared_property_value = getattr(doc, str(self.compared_property))
        return self.evaluate_expression()


class BooleanFormDataCaseIndicatorDefinition(FormDataInCaseIndicatorDefinition, BooleanIndicatorDefinitionMixin):
    """
        Evaluate boolean expression referencing a form property related to a form in a case.
    """
    def get_value_for_form(self, form_data):
        try:
            self._compared_property_value = self.get_from_form(form_data,
                self.compared_property.split('.'))
            return self.evaluate_expression()
        except Exception:
            return False


class PopulateRelatedCasesWithIndicatorDefinitionMixin(DocumentSchema):
    related_case_types = ListProperty()

    _related_cases = None
    def set_related_cases(self, case):
        """
            set _related_cases here.
            should be a list of CommCareCase objects
        """
        self._related_cases = list()

    def populate_with_value(self, value):
        """
            You shouldn't have to modify this.
        """
        for case in self._related_cases:
            if not isinstance(case, CommCareCase):
                continue
            try:
                namespace_computed = case.computed_.get(self.namespace, {})
                namespace_computed[self.slug] = value
                case.computed_[self.namespace] = namespace_computed
                case.computed_modified_on_ = datetime.datetime.utcnow()
                case.save()
            except Exception as e:
                logging.error("Could not populate indicator information to case %s due to error: %s" %
                    (case.get_id, e)
                )
