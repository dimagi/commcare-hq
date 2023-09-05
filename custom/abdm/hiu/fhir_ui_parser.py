import os

# Same package as used in HQ
from jsonpath_ng import parse as parse_jsonpath

from custom.abdm.utils import json_from_file

parser_config_json_file = 'fhir_ui_parser_config.json'
parser_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), parser_config_json_file)
parser_config = json_from_file(parser_config_path)


class FHIRUIConfigNotFound(Exception):
    pass


class JsonpathError(Exception):
    pass


def simplify_list(seq):
    if len(seq) == 1:
        return seq[0]
    if not seq:
        return None
    return seq


def resource_value_using_json_path(json_path, resource):
    try:
        jsonpath_expr = parse_jsonpath(json_path)
    except Exception as err:
        raise JsonpathError from err
    matches = jsonpath_expr.find(resource)
    values = [m.value for m in matches]
    return simplify_list(values)


def resources_dict_from_bundle(fhir_bundle):
    resource_type_to_resources = {}
    for entry in fhir_bundle["entry"]:
        resource_type_to_resources.setdefault(entry["resource"]["resourceType"], [])
        resource_type_to_resources[entry["resource"]["resourceType"]].append(entry["resource"])
    return resource_type_to_resources


def generate_display_fields_for_bundle(fhir_bundle, health_information_type):
    """
    Generates display fields to be used in UI based on config defined at 'fhir_ui_parser_config.json'.
    """
    health_information_ui_config = next(config for config in parser_config
                                        if config["health_information_type"] == health_information_type)
    if not health_information_ui_config:
        raise FHIRUIConfigNotFound(f"FHIR UI config not found for: '{health_information_type}'")
    resource_type_to_resources = resources_dict_from_bundle(fhir_bundle)
    parsed_result = []
    for config in health_information_ui_config["config"]:
        if not resource_type_to_resources.get(config["resource_type"]):
            continue
        for resource in resource_type_to_resources[config["resource_type"]]:
            for section in config["sections"]:
                data = {"section": section["section"], "resource": config['resource_type'], "entries": []}
                for section_entry in section["entries"]:
                    data_entry = {"label": section_entry["label"]}
                    # TODO Check if want to create multiple entries for multiple values
                    try:
                        data_entry["value"] = resource_value_using_json_path(section_entry["path"], resource)
                        if data_entry["value"]:
                            data["entries"].append(data_entry)
                        else:   # TODO Remove this
                            print(f"Value not found for section:{data['section']} and path:{section_entry['path']}")
                    except JsonpathError as err:
                        # TODO Use logging instead
                        print(f"Invalid path for {data['section']} and {section_entry['path']} and error: {err}")
                if data["entries"]:
                    parsed_result.append(data)
    return parsed_result
