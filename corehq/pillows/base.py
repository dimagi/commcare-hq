from pillowtop.listener import AliasedElasticPillow


VALUE_TAG = '#value'
DEFAULT_META = {
    "settings": {
        "analysis": {
            "analyzer": {
                "default": {
                    "type": "custom",
                    "tokenizer": "whitespace",
                    "filter": ["lowercase"]
                },
                "sortable_exact": {
                    "type": "custom",
                    "tokenizer": "keyword",
                    "filter": ["lowercase"]
                }
            }
        }
    }
}


def map_types(item, mapping, override_root_keys=None):
    if isinstance(item, dict):
        return convert_property_dict(item, mapping, override_root_keys=override_root_keys)
    elif isinstance(item, list):
        return [map_types(x, mapping) for x in item]
    else:
        return {VALUE_TAG: item}


def convert_property_dict(sub_dict, mapping, override_root_keys=None):
    """
    For mapping out ALL nested properties on cases, convert everything to a dict so as to
    prevent string=>object and object=>string mapping errors.

    sub_dict: the doc dict you want to modify in place before sending to ES
    mapping: The mapping at the level of the properties you are at - originally passing as the default mapping of the pillow
    override_root_keys: a list of keys you want explicitly skipped at the root level and are not recursed down
    """
    mapping = mapping or {}
    override_root_keys = override_root_keys or []

    for k, v in sub_dict.items():
        if k in mapping.get('properties', {}) or k in override_root_keys:
            continue
        dynamic_mapping = mapping.get('dynamic', True)
        sub_mapping = mapping.get('properties', {}).get(k, {})
        if dynamic_mapping is not False:
            sub_dict[k] = map_types(v, sub_mapping, override_root_keys=override_root_keys)
    return sub_dict


def restore_property_dict(report_dict_item):
    """
    Revert a converted/retrieved document from Report<index> and deconvert all its properties
    back from {#value: <val>} to just <val>
    """
    restored = {}
    if not isinstance(report_dict_item, dict):
        return report_dict_item

    for k, v in report_dict_item.items():
        if isinstance(v, list):
            restored[k] = [restore_property_dict(x) for x in v]
        elif isinstance(v, dict):
            if VALUE_TAG in v:
                restored[k] = v[VALUE_TAG]
            else:
                restored[k] = restore_property_dict(v)
        else:
            restored[k] = v

    return restored


class HQPillow(AliasedElasticPillow):
    es_timeout = 60
    es_meta = DEFAULT_META
