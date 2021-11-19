from corehq.pillows.core import DATE_FORMATS_STRING, DATE_FORMATS_ARR
from corehq.util.elastic import prefix_for_tests
from pillowtop.es_utils import ElasticsearchIndexInfo, REPORT_XFORM_HQ_INDEX_NAME

REPORT_XFORM_INDEX = prefix_for_tests("report_xforms_20160824_1708")

REPORT_XFORM_MAPPING = {
    "_meta": {
        "created": "2014-10-07"  # record keeping on the index.
    },
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR,  # for parsing the explicitly defined dates
    "dynamic": True,
    "dynamic_templates": [
        {
            "case_block": {
                "mapping": {  # case mapping fragment
                    "dynamic": False,
                    "type": "nested",
                    "properties": {
                        "@case_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "@date_modified": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "@user_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "@xmlns": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "attachment": {
                            "dynamic": False,
                            "type": "object"
                        },
                        "case_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "create": {
                            "dynamic": True,
                            "type": "object",
                            "properties": {
                                "case_name": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                },
                                "case_type": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                },
                                "owner_id": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                }
                            }
                        },
                        "date_modified": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "index": {
                            "dynamic": True,
                            "type": "object"
                        },
                        "update": {
                            "dynamic": True,
                            "type": "object",
                            "properties": {
                                "case_name": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                },
                                "case_type": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                },
                                "date_opened": {
                                    "format": DATE_FORMATS_STRING,
                                    "type": "date"
                                },
                                "owner_id": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                }
                            }
                        },
                        "user_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "xmlns": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    }
                },
                "match": "case"
            }
        },
        {
            "everything_else": {
                "mapping": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "match": "*",
                "match_mapping_type": "string"
            }
        }
    ],
    "properties": {
        "#export_tag": {
            "index": "not_analyzed",
            "type": "string"
        },
        "@uiVersion": {
            "type": "string"
        },
        "@version": {
            "type": "string"
        },
        "_attachments": {
            "dynamic": False,
            "type": "object"
        },
        "app_id": {
            "index": "not_analyzed",
            "type": "string"
        },
        "doc_type": {
            "type": "string"
        },
        "domain": {
            "fields": {
                "domain": {
                    "index": "analyzed",
                    "type": "string"
                },
                "exact": {
                    # exact is full text string match - hyphens get parsed in standard
                    # analyzer
                    # in queries you can access by domain.exact
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "multi_field"
        },
        "external_blobs": {
            "dynamic": False,
            "type": "object"
        },
        "form": {
            "dynamic": True,
            "properties": {
                "#type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "@name": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "meta": {
                    "dynamic": False,
                    "properties": {
                        "CommCareVersion": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "appVersion": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "deviceID": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "instanceID": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "timeEnd": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "timeStart": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "userID": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "username": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    }
                }
            }
        },
        "initial_processing_complete": {
            "type": "boolean"
        },
        "partial_submission": {
            "type": "boolean"
        },
        "path": {
            "index": "not_analyzed",
            "type": "string"
        },
        "received_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "submit_ip": {
            "type": "ip"
        },
        "xmlns": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "xmlns": {
                    "index": "analyzed",
                    "type": "string"
                }
            },
            "type": "multi_field"
        }
    }
}

REPORT_XFORM_ALIAS = prefix_for_tests("report_xforms")
REPORT_XFORM_TYPE = "report_xform"

REPORT_XFORM_INDEX_INFO = ElasticsearchIndexInfo(
    index=REPORT_XFORM_INDEX,
    alias=REPORT_XFORM_ALIAS,
    type=REPORT_XFORM_TYPE,
    mapping=REPORT_XFORM_MAPPING,
    hq_index_name=REPORT_XFORM_HQ_INDEX_NAME
)
