from corehq.apps.reports.util import get_INFilter_element_bindparam
from dimagi.utils.couch.database import get_db
from corehq.apps.domain.utils import DOMAIN_MODULE_KEY
import fluff


def flat_field(fn):
    def getter(item):
        return unicode(fn(item) or "")
    return fluff.FlatField(getter)


def add_to_module_map(domain, module):
    db = get_db()
    if db.doc_exist(DOMAIN_MODULE_KEY):
        module_config = db.open_doc(DOMAIN_MODULE_KEY)
        module_map = module_config.get('module_map')
        if module_map:
            module_map[domain] = module
        else:
            module_config['module_map'][domain] = module
    else:
        module_config = db.save_doc(
            {
                '_id': DOMAIN_MODULE_KEY,
                'module_map': {
                    domain: module
                }
            }
        )
    db.save_doc(module_config)


def clean_IN_filter_value(filter_values, filter_value_name):
    if filter_value_name in filter_values:
        for i, val in enumerate(filter_values[filter_value_name]):
            filter_values[get_INFilter_element_bindparam(filter_value_name, i)] = val
        del filter_values[filter_value_name]
    return filter_values
