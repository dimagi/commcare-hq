from django.utils.text import slugify

from corehq.apps.app_manager.app_schemas.case_properties import (
    ParentCasePropertyBuilder,
    get_usercase_properties,
)
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.app_manager.templatetags.xforms_extras import clean_trans
from corehq.apps.app_manager.util import is_usercase_in_use
from corehq.apps.data_dictionary.util import get_case_property_description_dict
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.privileges import DATA_DICTIONARY


def get_casedb_schema(form):
    """Get case database schema definition for vellum to display as an external data source.

    This lists all case types and their properties for the given app.
    """
    app = form.get_app()

    subsets = []
    if form.requires_case() and not form.get_module().search_config.data_registry:
        subsets.extend(_get_case_schema_subsets(app, form.get_module().case_type))

    parent_select = getattr(form.get_module(), 'parent_select', None)
    if parent_select and parent_select.active and parent_select.relationship is None:
        # for child modules that use parent select where the parent is not a 'related' case
        # See toggles.NON_PARENT_MENU_SELECTION
        parent_module = app.get_module_by_unique_id(parent_select.module_id)
        source = clean_trans(parent_module.name, app.langs)
        subsets.extend(_get_case_schema_subsets(app, parent_module.case_type, source=source))

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


def get_registry_schema(form):
    """Get registry database schema definition for vellum to display as an external data source.

    This lists all case types and their properties for the given app.
    """
    app = form.get_app()
    module = form.get_module()
    data_registry = module.search_config.data_registry

    subsets = []
    if form.requires_case() and data_registry:
        subsets.extend(_get_case_schema_subsets(app, module.case_type, hashtag='#registry_case/'))

    return {
        "id": "registry",
        "uri": "jr://instance/remote/registry",
        "name": "registry_case",
        "path": "/results/case",
        "structure": {},
        "subsets": subsets,
    }


def _get_case_schema_subsets(app, base_case_type, hashtag='#case/', source=None):
    builder = ParentCasePropertyBuilder.for_app(app, ['case_name'], include_parent_properties=False)
    related = builder.get_parent_type_map(None)
    map = builder.get_properties_by_case_type()
    if domain_has_privilege(app.domain, DATA_DICTIONARY):
        descriptions_dict = get_case_property_description_dict(app.domain)
    else:
        descriptions_dict = {}

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

    name_source = f" - {source}" if source else ""
    id_source = f":{slugify(source)}" if source else ""
    hashtag = f"{hashtag}{id_source}"

    def _name(i, ctypes):
        if i > 0:
            return "{} ({}){}".format(generation_names[i], " or ".join(ctypes), name_source)
        return f"{base_case_type}{name_source}"

    return [{
        "id": f"{generation_names[i]}{id_source}",
        "name": _name(i, ctypes),
        "structure": {
            p: {"description": descriptions_dict.get(t, {}).get(p, '')}
            for t in ctypes for p in map[t]},
        "related": {"parent": {
            "hashtag": hashtag + generation_names[i + 1],
            "subset": f"{generation_names[i + 1]}{id_source}",
            "key": "@case_id",
        }} if i < len(generations) - 1 else None,
    } for i, ctypes in enumerate(generations)]
