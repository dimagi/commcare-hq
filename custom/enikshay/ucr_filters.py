from collections import namedtuple

from sqlagg.filters import ORFilter, EQFilter

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.es import filters
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports_core.filters import DynamicChoiceListFilter
from corehq.apps.userreports.reports.filters.choice_providers import LocationChoiceProvider
from corehq.apps.userreports.reports.filters.specs import FilterSpec
from corehq.apps.userreports.reports.filters.values import FilterValue, dynamic_choice_list_url

_LocationFilter = namedtuple("_LocationFilter", "column parameter_slug filter_value")


class ENikshayLocationHierarchyFilterValue(FilterValue):

    @memoized
    def get_hierarchy(self, location_id):
        """
        Return a list of _LocationFilter(column, parameter_slug, filter_value) objects to be used in constructing
        the filter.
        """
        location = SQLLocation.objects.get(location_id=location_id)
        filters = []
        for ancestor in location.get_ancestors():
            column = ancestor.location_type.name
            parameter = "{slug}_{column}".format(slug=self.filter.slug, column=column)
            value = ancestor.location_id
            filters.append(
                _LocationFilter(column, parameter, value)
            )

        below_column = "below_{}".format(location.location_type.name)
        below_parameter = "{slug}_{column}".format(slug=self.filter.slug, column=below_column)
        filters.append(
            _LocationFilter(below_column, below_parameter, location.location_id)
        )
        return filters

    def to_sql_filter(self):
        location_id = self.value[0].value
        return ORFilter([
            EQFilter(x.column, x.parameter_slug) for x in self.get_hierarchy(location_id)
        ])

    def to_sql_values(self):
        location_id = self.value[0].value
        return {
            x.parameter_slug: x.filter_value for x in self.get_hierarchy(location_id)
        }

    def to_es_filter(self):
        location_id = self.value[0].value
        fs = [
            filters.term(x.column, x.filter_value) for x in self.get_hierarchy(location_id)
        ]
        return filters.OR(fs)


class EnikshayLocationHiearachyFilter(DynamicChoiceListFilter):
    """
    A custom ucr report filter for the enikshay Referral Report.
    This filter will use the selected filter to filter against multiple fields.
    https://docs.google.com/document/d/1ejESqYoqSff0u4X72Fq0TYi7ll3IvH5KX3VWXzLyMQs/edit

    Each referral in the data source has fields like:
        cto
        dto
        sto
        ...
        below_cto
        below_dto
        below_sto
        ...
    corresponding to the location hieararchy levels.
    If a person was referred to a location below a given level, then the below_<location_level> column will
    contain the id of the location at <location_level>. The <location_level> column corresponding to the location
    that the person was referred to will contain the location id, and the other location level columns will be
    blank.
    """

    def __init__(self, name, label, choice_provider, url_generator, css_id=None):

        super(EnikshayLocationHiearachyFilter, self).__init__(
            name=name,
            field=None,
            datatype="string",
            label=label,
            show_all=None,
            choice_provider=choice_provider,
            url_generator=url_generator,
            css_id=css_id,
        )


def _build_enikshay_location_hierarchy(spec, report):
    wrapped = FilterSpec.wrap(spec)
    choice_provider = LocationChoiceProvider(report, wrapped.slug)
    choice_provider.configure({})
    return EnikshayLocationHiearachyFilter(
        name=wrapped.slug,
        label=wrapped.get_display(),
        choice_provider=choice_provider,
        url_generator=dynamic_choice_list_url,
    )
