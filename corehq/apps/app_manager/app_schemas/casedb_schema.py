from __future__ import absolute_import
from __future__ import unicode_literals
from corehq import toggles
from corehq.apps.app_manager.app_schemas.case_properties import get_shared_case_types, \
    get_per_type_defaults, ParentCasePropertyBuilder, get_usercase_properties
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.util import is_usercase_in_use
from corehq.apps.data_dictionary.util import get_case_property_description_dict


def get_casedb_schema(form):
    """Get case database schema definition for vellum to display as an external data source.

    This lists all case types and their properties for the given app.
    """
    app = form.get_app()
    base_case_type = form.get_module().case_type if form.requires_case() else None
    case_types = app.get_case_types() | get_shared_case_types(app)
    per_type_defaults = get_per_type_defaults(app.domain, case_types)
    builder = ParentCasePropertyBuilder(app, ['case_name'], per_type_defaults)
    related = builder.get_parent_type_map(case_types, allow_multiple_parents=True)
    map = builder.get_case_property_map(case_types, include_parent_properties=False)
    descriptions_dict = get_case_property_description_dict(app.domain)

    if base_case_type:
        # Generate hierarchy of case types, represented as a list of lists of strings:
        # [[base_case_type], [parent_type1, parent_type2...], [grandparent_type1, grandparent_type2...]]
        # Vellum case management only supports three levels
        generation_names = ['case', 'parent', 'grandparent']
        generations = [[] for g in generation_names]

        def _add_ancestors(ctype, generation):
            if generation < len(generation_names):
                generations[generation].append(ctype)
                for parent in related.get(ctype, {}).get('parent', []):
                    _add_ancestors(parent, generation + 1)

        _add_ancestors(base_case_type, 0)

        # Remove any duplicate types or empty generations
        generations = [set(g) for g in generations if len(g)]
    else:
        generations = []

    subsets = [{
        "id": generation_names[i],
        "name": "{} ({})".format(generation_names[i], " or ".join(ctypes)) if i > 0 else base_case_type,
        "structure": {
            p: {"description": descriptions_dict.get(t, {}).get(p, '')}
            for t in ctypes for p in map[t]},
        "related": {"parent": {
            "hashtag": "#case/" + generation_names[i + 1],
            "subset": generation_names[i + 1],
            "key": "@case_id",
        }} if i < len(generations) - 1 else None,
    } for i, ctypes in enumerate(generations)]

    if is_usercase_in_use(app.domain):
        subsets.append({
            "id": USERCASE_TYPE,
            "name": "user",
            "key": "@case_type",
            "structure": {p: {} for p in get_usercase_properties(app)[USERCASE_TYPE]},
        })

    return {
        "id": "casedb",
        "uri": "jr://instance/casedb",
        "name": "case",
        "path": "/casedb/case",
        "structure": {},
        "subsets": subsets,
    }
