from __future__ import absolute_import
from __future__ import print_function
import json

from django.core.management.base import BaseCommand


def get_below_location_level_indicator(location_level):
    return {
        "create_index": True,
        "display_name": "below_{}".format(location_level),
        "datatype": "string",
        "type": "expression",
        "column_id": "below_{}".format(location_level),
        "expression": {
            "type": "conditional",
            "test": {
                "type": "boolean_expression",
                "operator": "in",
                "expression": {
                    "type": "ancestor_location",
                    "location_id": {
                        "type": "enikshay_referred_to",
                        "person_id_expression": {
                            "type": "property_name",
                            "property_name": "_id",
                        }
                    },
                    "location_type": location_level,
                },
                "property_value": [
                    "",
                    None
                ]
            },
            "expression_if_true": "",
            "expression_if_false": {
                "type": "nested",
                "argument_expression": {
                    "type": "ancestor_location",
                    "location_id": {
                        "type": "enikshay_referred_to",
                        "person_id_expression": {
                            "type": "property_name",
                            "property_name": "_id",
                        }
                    },
                    "location_type": location_level,
                },
                "value_expression": {
                    "type": "property_name",
                    "property_name": "location_id",
                }
            },
        }
    }


def get_location_level_indicator(location_level):
    return {
        "create_index": True,
        "display_name": location_level,
        "datatype": "string",
        "type": "expression",
        "column_id": location_level,
        "expression": {
            "type": "related_doc",
            "related_doc_type": "Location",
            "doc_id_expression": {
                "type": "enikshay_referred_to",
                "person_id_expression": {
                    "type": "property_name",
                    "property_name": "_id",
                }
            },
            "value_expression": {
                "type": "conditional",
                "test": {
                    "operator": "eq",
                    "expression": {
                        "type": "property_name",
                        "property_name": "location_type"
                    },
                    "type": "boolean_expression",
                    "property_value": location_level
                },
                "expression_if_true": {
                    "type": "property_name",
                    "property_name": "location_id"
                },
                "expression_if_false": {
                    "type": "constant",
                    "constant": "",
                }
            }
        }
    }


def get_referred_to_expression():
    return {
        "type": "enikshay_referred_to",
        "person_id_expression": {
            "type": "property_name",
            "property_name": "_id"
        }
    }


def get_referred_by_expression():
    # Referred_by is either a location_id (if we are getting the data from a trail)
    # or it is a user_id (if we are getting the data from a referral)

    referred_by_expression = {
        "type": "enikshay_referred_by",
        "person_id_expression": {
            "type": "property_name",
            "property_name": "_id"
        }
    }
    referral_referred_by_expression = {
        "type": "related_doc",
        "related_doc_type": "CommCareUser",
        "doc_id_expression": referred_by_expression,
        "value_expression": {
            "type": "property_name",
            "property_name": "location_id"
        }
    }

    return {
        "type": "conditional",
        "test": {
            # Check if there is a corresponding user with the id
            "operator": "in",
            "type": "boolean_expression",
            "property_value": ["", None, "None", "null"],
            "expression": referral_referred_by_expression
        },
        # If there isn't, referred_by_expression must be yielding a location id
        "expression_if_true": referred_by_expression,
        # If there is, return the user's location id
        "expression_if_false": referral_referred_by_expression,
    }


def location_name_from_json(json_expression):
    """
    Given an expression that returns the json of a location, return an expression that yields the the location_name
    """
    return {
        "type": "nested",
        "argument_expression": json_expression,
        "value_expression": {
            "type": "property_name",
            "property_name": "name"
        }
    }


def location_name(location_id_expression):
    value_expression = {
        "type": "property_name",
        "property_name": "name"
    }
    return location(location_id_expression, value_expression)


def location_type_name(location_id_expression):
    return {
        "type": "location_type_name",
        "location_id_expression": location_id_expression
    }


def location(location_id_expression, value_expression):
    return {
        "type": "related_doc",
        "related_doc_type": "Location",
        "doc_id_expression": location_id_expression,
        "value_expression": value_expression
    }


def concatenate_expressions(expressions):
    return {
        'type': 'concatenate_strings',
        'expressions': expressions,
        "separator": ', '
    }


def full_name(location_id_expression):
    """
    Return an expression that returns the full name of the location specified by the given location id expression.

    Full name is in one of these formats (depending on where the location is in the hierarchy:
        <district name>, <tu name>, <phi name>
        <district name>, <tu name>
        <location name>
    """
    full_name_expression = {
        "type": "switch",
        "switch_on": location_type_name(location_id_expression),
        "cases": {
            "tu": concatenate_expressions([
                location_name_from_json({
                    "type": "ancestor_location",
                    "location_type": "dto",
                    "location_id": location_id_expression
                }),
                location_name(location_id_expression)
            ]),
            "phi": concatenate_expressions([
                location_name_from_json({
                    "type": "ancestor_location",
                    "location_type": "dto",
                    "location_id": location_id_expression
                }),
                location_name_from_json({
                    "type": "ancestor_location",
                    "location_type": "tu",
                    "location_id": location_id_expression
                }),
                location_name(location_id_expression)
            ])
        },
        "default": location_name(location_id_expression)
    }
    return {
        "type": "conditional",
        "test": {
            "operator": "in",
            "type": "boolean_expression",
            "property_value": ["", None, "None", "null"],
            "expression": location_id_expression
        },
        "expression_if_true": "",
        "expression_if_false": full_name_expression,
    }


def get_referred_by_name_indicator():
    return {
        "column_id": "referred_by_name",
        "display_name": "referred_by_name",
        "create_index": False,
        "datatype": "string",
        "type": "expression",
        "expression": full_name(get_referred_by_expression())
    }


def get_referred_to_name_indicator():
    return {
        "column_id": "referred_to_name",
        "display_name": "referred_to_name",
        "create_index": False,
        "datatype": "string",
        "type": "expression",
        "expression": full_name(get_referred_to_expression())
    }


def dump(d):
    return json.dumps(d, indent=2)


class Command(BaseCommand):
    """
    Just a little script to make writing data source indicators less painful.
    This script was used to generate several of the indicators in person_for_referral_report.json, and can be used
    again if changed need to be made.
    """

    def handle(self, **options):
        location_levels = [
            "sto",
            "cto",
            "dto",
            "tu",
            "phi",
        ]
        for location_level in location_levels:
            print(dump(get_location_level_indicator(location_level)) + ",")
            print(dump(get_below_location_level_indicator(location_level)) + ",")

        print(dump(get_referred_by_name_indicator()) + ", ")
        print(dump(get_referred_to_name_indicator()))
