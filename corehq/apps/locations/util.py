from corehq.apps.locations.models import Location, root_locations

def load_locs_json(domain, selected_loc_id=None):
    """initialize a json location tree for drill-down controls on
    the client. tree is only partially initialized and branches
    will be filled in on the client via ajax.

    what is initialized:
    * all top level locs
    * if a 'selected' loc is provided, that loc and its complete
      ancestry
    """
    def loc_to_json(loc):
        return {
            'name': loc.name,
            'location_type': loc.location_type,
            'uuid': loc._id,
        }
    loc_json = [loc_to_json(loc) for loc in root_locations(domain)]

    # if a location is selected, we need to pre-populate its location hierarchy
    # so that the data is available client-side to pre-populate the drop-downs
    if selected_loc_id:
        selected = Location.get(selected_loc_id)
        lineage = list(Location.view('_all_docs', keys=selected.path, include_docs=True))

        parent = {'children': loc_json}
        for loc in lineage:
            # find existing entry in the json tree that corresponds to this loc
            this_loc = [k for k in parent['children'] if k['uuid'] == loc._id][0]
            this_loc['children'] = [loc_to_json(loc) for loc in loc.children]
            parent = this_loc

    return loc_json
  
# hard-coded for now
def allowed_child_types(domain, parent):
    parent_type = parent.location_type if parent else None

    return {
        None: ['state'],
        'state': ['district'],
        'district': ['block'],
        'block': ['village', 'outlet'],
        'village': ['outlet'],
        'outlet': [],
     }[parent_type]
