from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.reports_core.filters import DynamicChoiceListFilter
from corehq.apps.userreports.reports.filters.factory import FilterChoiceProviderFactory
from corehq.apps.userreports.reports.filters.values import dynamic_choice_list_url
from corehq.apps.userreports.reports.filters.specs import DynamicChoiceListFilterSpec
from corehq.apps.userreports.specs import TypeProperty


class VillageChoiceListFilterSpec(DynamicChoiceListFilterSpec):
    """Using this filter allows us to filter by village without introducing a
    data source change to include the village in the data source.

    It does this by finding the case ids that belong to the village and
    filtering on the doc_id column instead of a location column

    This would likely be very inefficient to do at scale, but should be ok for
    a pilot
    """
    type = TypeProperty('village_choice_list')


def build_village_choice_list_filter_spec(spec, report):
    wrapped = VillageChoiceListFilterSpec.wrap(spec)
    choice_provider_spec = {"type": "location"}
    choice_provider = FilterChoiceProviderFactory.from_spec(choice_provider_spec)(report, wrapped.slug)
    choice_provider.configure(choice_provider_spec)

    return DynamicChoiceListFilter(
        name=wrapped.slug,
        datatype=wrapped.datatype,
        field=wrapped.field,
        label=wrapped.display,
        show_all=wrapped.show_all,
        url_generator=dynamic_choice_list_url,
        choice_provider=choice_provider,
        ancestor_expression=wrapped.ancestor_expression,
    )
