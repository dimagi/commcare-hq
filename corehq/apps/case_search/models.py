from dimagi.ext import jsonobject
from django.db import models
from jsonfield.fields import JSONField


CLAIM_CASE_TYPE = 'commcare-case-claim'
FUZZY_PROPERTIES = "fuzzy_properties"


class FuzzyProperties(jsonobject.JsonObject):
    case_type = jsonobject.StringProperty()
    properties = jsonobject.ListProperty(unicode)


class CaseSearchConfigJSON(jsonobject.JsonObject):
    fuzzy_properties = jsonobject.ListProperty(FuzzyProperties)

    def add_fuzzy_property(self, case_type, property):
        self.add_fuzzy_properties(case_type, [property])

    def add_fuzzy_properties(self, case_type, properties):
        for prop in self.fuzzy_properties:
            if prop.case_type == case_type:
                prop.properties = list(set(prop.properties) | set(properties))
                return

        self.fuzzy_properties = self.fuzzy_properties + [
            FuzzyProperties(case_type=case_type, properties=properties)
        ]

    def remove_fuzzy_property(self, case_type, property):
        for prop in self.fuzzy_properties:
            if prop.case_type == case_type and property in prop.properties:
                prop.properties = list(set(prop.properties) - set([property]))
                return

        raise AttributeError("{} is not a fuzzy property for {}".format(property, case_type))

    def get_fuzzy_properties_for_case_type(self, case_type):
        """
        Returns a list of search properties to be fuzzy searched
        """
        for prop in self.fuzzy_properties:
            if prop.case_type == case_type:
                return prop.properties
        return []


class GetOrNoneManager(models.Manager):
    """
    Adds get_or_none method to objects
    """

    def get_or_none(self, **kwargs):
        try:
            return self.get(**kwargs)
        except self.model.DoesNotExist:
            return None


class CaseSearchConfig(models.Model):
    """
    Contains config for case search
    """
    class Meta:
        app_label = 'case_search'

    domain = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        db_index=True,
        primary_key=True
    )
    enabled = models.BooleanField(blank=False, null=False, default=False)
    _config = JSONField(default=dict)

    objects = GetOrNoneManager()

    @classmethod
    def enabled_domains(cls):
        return cls.objects.filter(enabled=True).values_list('domain', flat=True)

    @property
    def config(self):
        return CaseSearchConfigJSON.wrap(self._config)

    @config.setter
    def config(self, value):
        assert isinstance(value, CaseSearchConfigJSON)
        self._config = value.to_json()


def case_search_enabled_for_domain(domain):
    try:
        CaseSearchConfig.objects.get(pk=domain, enabled=True)
    except CaseSearchConfig.DoesNotExist:
        return False
    else:
        return True


def enable_case_search(domain):
    from corehq.apps.case_search.tasks import reindex_case_search_for_domain
    config, created = CaseSearchConfig.objects.get_or_create(pk=domain)
    if not config.enabled:
        config.enabled = True
        config.save()
        reindex_case_search_for_domain.delay(domain)


def disable_case_search(domain):
    from corehq.apps.case_search.tasks import delete_case_search_cases_for_domain
    try:
        config = CaseSearchConfig.objects.get(pk=domain)
    except CaseSearchConfig.DoesNotExist:
        # CaseSearch was never enabled
        return
    if config.enabled:
        config.enabled = False
        config.save()
        delete_case_search_cases_for_domain.delay(domain)


def case_search_enabled_domains():
    """Returns a list of all domains that have case search enabled
    """
    return CaseSearchConfig.objects.filter(enabled=True).values_list('domain', flat=True)
