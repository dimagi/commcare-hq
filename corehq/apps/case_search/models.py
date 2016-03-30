from django.db import models
from jsonfield.fields import JSONField

FUZZY_PROPERTIES = "fuzzy_properties"


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
    config = JSONField(default={})

    @classmethod
    def enabled_domains(cls):
        return cls.objects.filter(enabled=True).values_list('domain', flat=True)

    def add_fuzzy_property(self, case_type, property):
        """
        Adds a case property to be fuzzy searched with CaseSearchES

        Case Properties set as fuzzy will use a fuzzy search flag in ES.
        Should only really be set for text properties.
        Fuzzy properties add the following to the config JSON:
        {
            "fuzzy_properties":[
                {
                    "case_type": "pirates",
                    "properties": ["name", "age"]
                },
                {
                    "case_type": "swashbucklers",
                    "properties": ["has_parrot"]
                }
            ]
        }
        """
        self.add_fuzzy_properties(case_type, [property])

    def add_fuzzy_properties(self, case_type, properties):
        """
        Adds a list of case-properties to be fuzzy searched
        """
        fuzzy_params = self.config.get(FUZZY_PROPERTIES, [])
        for prop in fuzzy_params:
            if prop['case_type'] == case_type:
                prop['properties'] = list(set(prop['properties']) | set(properties))
                return

        fuzzy_params.append({'case_type': case_type, 'properties': properties})
        self.config[FUZZY_PROPERTIES] = fuzzy_params

    def remove_fuzzy_property(self, case_type, property):
        """
        Removes fuzzy search properties
        """
        fuzzy_params = self.config.get(FUZZY_PROPERTIES, [])
        for prop in fuzzy_params:
            if prop['case_type'] == case_type:
                if property in prop['properties']:
                    prop['properties'] = list(set(prop['properties']) - set([property]))
                    return

        raise AttributeError("{} is not a fuzzy property for {}".format(property, case_type))

    def fuzzy_properties_for_case_type(self, case_type):
        """
        Returns a list of search properties to be fuzzy searched
        """
        try:
            fuzzy_params = self.config[FUZZY_PROPERTIES]
            for prop in fuzzy_params:
                if prop['case_type'] == case_type:
                    return prop['properties']
        except KeyError:
            return []
        return []


def case_search_enabled_for_domain(domain):
    try:
        CaseSearchConfig.objects.get(pk=domain, enabled=True)
    except CaseSearchConfig.DoesNotExist:
        return False
    else:
        return True
