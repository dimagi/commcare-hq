from corehq.apps.locations.models import SQLLocation


def get_relevant_supply_point_ids(domain, active_location=None):
    """
    Return a list of supply point ids for the selected location
    and all of its descendants OR all supply point ids in the domain.
    """
    def filter_relevant(queryset):
        return queryset.filter(
            supply_point_id__isnull=False
        ).values_list(
            'supply_point_id',
            flat=True
        )

    if active_location:
        sql_location = active_location.sql_location
        supply_point_ids = []
        if sql_location.supply_point_id:
            supply_point_ids.append(sql_location.supply_point_id)
        supply_point_ids += list(
            filter_relevant(sql_location.get_descendants())
        )

        return supply_point_ids
    else:
        return filter_relevant(SQLLocation.objects.filter(domain=domain))
