from corehq.util.elastic import prefix_for_tests
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from pillowtop.es_utils import ElasticsearchIndexInfo, APP_HQ_INDEX_NAME

APP_INDEX = prefix_for_tests("hqapps_2020-02-26")
APP_ES_ALIAS = prefix_for_tests("hqapps")
APP_ES_TYPE = "app"

APP_MAPPING = {
    "date_formats": DATE_FORMATS_ARR,
    "dynamic": False,
    "_meta": {
        "created": None
    },
    "_all": {
        "enabled": False
    },
    "date_detection": False,
    "properties": {
        "@indexed_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "short_url": {
            "type": "string",
            "index": "not_analyzed"
        },
        "build_broken": {
            "type": "boolean"
        },
        "copy_of": {
            "type": "string",
            "index": "not_analyzed"
        },
        "phone_model": {
            "type": "string"
        },
        "copy_history": {
            "type": "string"
        },
        "is_released": {
            "type": "boolean"
        },
        "platform": {
            "type": "string"
        },
        "admin_password": {
            "type": "string"
        },
        "build_spec": {
            "type": "object",
            "dynamic": False,
            "properties": {
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "version": {
                    "type": "string"
                },
                "build_number": {
                    "type": "long"
                },
                "latest": {
                    "type": "boolean"
                }
            }
        },
        "success_message": {
            "type": "object",
            "dynamic": False
        },
        "multimedia_map": {
            "type": "object",
            "dynamic": False,
            "properties": {
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "version": {
                    "type": "long"
                },
                "multimedia_id": {
                    "type": "string"
                },
                "media_type": {
                    "type": "string"
                },
                "unique_id": {
                    "type": "string"
                }
            }
        },
        "comment_from": {
            "type": "string"
        },
        "cloudcare_enabled": {
            "type": "boolean"
        },
        "recipients": {
            "type": "string"
        },
        "translations": {
            "type": "object",
            "dynamic": False
        },
        "built_on": {
            "type": "date",
            "format": DATE_FORMATS_STRING
        },
        "built_with": {
            "type": "object",
            "dynamic": False,
            "properties": {
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "build_number": {
                    "type": "long"
                },
                "signed": {
                    "type": "boolean"
                },
                "datetime": {
                    "type": "date",
                    "format": DATE_FORMATS_STRING
                },
                "version": {
                    "type": "string"
                },
                "latest": {
                    "type": "boolean"
                }
            }
        },
        "application_version": {
            "type": "string"
        },
        "build_comment": {
            "type": "string"
        },
        "doc_type": {
            "index": "not_analyzed",
            "type": "string"
        },
        "name": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "force_http": {
            "type": "boolean"
        },
        "created_from_template": {
            "type": "string"
        },
        "translation_strategy": {
            "type": "string"
        },
        "case_sharing": {
            "type": "boolean"
        },
        "short_odk_url": {
            "type": "string",
            "index": "not_analyzed"
        },
        "domain": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "build_langs": {
            "type": "string",
            "index": "not_analyzed"
        },
        "deployment_date": {
            "type": "date",
            "format": DATE_FORMATS_STRING
        },
        "user_type": {
            "type": "string"
        },
        "text_input": {
            "type": "string"
        },
        "secure_submissions": {
            "type": "boolean"
        },
        "build_signed": {
            "type": "boolean"
        },
        "vellum_case_management": {
            "type": "boolean"
        },
        "family_id": {
            "type": "string"
        },
        "upstream_version": {
            "type": "long"
        },
        "upstream_app_id": {
            "type": "string"
        },
        "version": {
            "type": "long"
        },
        "profile": {
            "type": "object",
            "dynamic": True
        },
        "description": {
            "type": "string"
        },
        "short_odk_media_url": {
            "type": "string",
            "index": "not_analyzed"
        },
        "langs": {
            "type": "string",
            "index": "not_analyzed"
        },
        "use_custom_suite": {
            "type": "boolean"
        },
        "cached_properties": {
            "type": "object",
            "dynamic": False
        },
        "modules": {
            "type": "nested",
            "dynamic": False,
            "properties": {
                "case_list": {
                    "type": "object",
                    "dynamic": False,
                    "properties": {
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "show": {
                            "type": "boolean"
                        },
                        "label": {
                            "type": "object",
                            "dynamic": False
                        }
                    }
                },
                "put_in_root": {
                    "type": "boolean"
                },
                "root_module_id": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "name": {
                    "type": "object",
                    "dynamic": False
                },
                "referral_list": {
                    "type": "object",
                    "dynamic": False,
                    "properties": {
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "show": {
                            "type": "boolean"
                        },
                        "label": {
                            "type": "object",
                            "dynamic": False
                        }
                    }
                },
                "parent_select": {
                    "type": "object",
                    "dynamic": False,
                    "properties": {
                        "active": {
                            "type": "boolean"
                        },
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "relationship": {
                            "type": "string"
                        },
                        "module_id": {
                            "type": "string"
                        }
                    }
                },
                "forms": {
                    "type": "nested",
                    "dynamic": False,
                    "properties": {
                        "unique_id": {
                            "type": "string",
                            "index": "not_analyzed"
                        },
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "version": {
                            "type": "long"
                        },
                        "name": {
                            "type": "object",
                            "dynamic": False
                        },
                        "show_count": {
                            "type": "boolean"
                        },
                        "form_type": {
                            "type": "string"
                        },
                        "requires": {
                            "type": "string"
                        },
                        "form_filter": {
                            "type": "string"
                        },
                        "actions": {
                            "type": "object",
                            "dynamic": False,
                            "properties": {
                                "subcases": {
                                    "type": "nested",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "repeat_context": {
                                            "type": "string"
                                        },
                                        "case_properties": {
                                            "type": "object",
                                            "dynamic": False
                                        },
                                        "case_type": {
                                            "type": "string"
                                        },
                                        "reference_id": {
                                            "type": "string"
                                        },
                                        "case_name": {
                                            "type": "string"
                                        },
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {
                                                    "type": "string"
                                                },
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {
                                                    "type": "string"
                                                },
                                                "type": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    }
                                },
                                "update_case": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "update": {
                                            "type": "object",
                                            "dynamic": False
                                        },
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {
                                                    "type": "string"
                                                },
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {
                                                    "type": "string"
                                                },
                                                "type": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    }
                                },
                                "close_referral": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {
                                                    "type": "string"
                                                },
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {
                                                    "type": "string"
                                                },
                                                "type": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    }
                                },
                                "open_referral": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "name_path": {
                                            "type": "string"
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "followup_date": {
                                            "type": "string"
                                        },
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {
                                                    "type": "string"
                                                },
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {
                                                    "type": "string"
                                                },
                                                "type": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    }
                                },
                                "case_preload": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "preload": {
                                            "type": "object",
                                            "dynamic": False
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {
                                                    "type": "string"
                                                },
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {
                                                    "type": "string"
                                                },
                                                "type": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    }
                                },
                                "doc_type": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                },
                                "load_from_form": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "preload": {
                                            "type": "object",
                                            "dynamic": False
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {
                                                    "type": "string"
                                                },
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {
                                                    "type": "string"
                                                },
                                                "type": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    }
                                },
                                "open_case": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "name_path": {
                                            "type": "string"
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "external_id": {
                                            "type": "string"
                                        },
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {
                                                    "type": "string"
                                                },
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {
                                                    "type": "string"
                                                },
                                                "type": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    }
                                },
                                "update_referral": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "followup_date": {
                                            "type": "string"
                                        },
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {
                                                    "type": "string"
                                                },
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {
                                                    "type": "string"
                                                },
                                                "type": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    }
                                },
                                "referral_preload": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "preload": {
                                            "type": "object",
                                            "dynamic": False
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {
                                                    "type": "string"
                                                },
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {
                                                    "type": "string"
                                                },
                                                "type": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    }
                                },
                                "close_case": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {
                                                    "type": "string"
                                                },
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {
                                                    "type": "string"
                                                },
                                                "type": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "xmlns": {
                            "type": "string",
                            "index": "not_analyzed"
                        }
                    }
                },
                "case_type": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "type": "string"
                },
                "details": {
                    "type": "object",
                    "dynamic": False,
                    "properties": {
                        "filter": {
                            "type": "string"
                        },
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "type": {
                            "type": "string"
                        },
                        "sort_elements": {
                            "type": "object",
                            "dynamic": False,
                            "properties": {
                                "doc_type": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                },
                                "direction": {
                                    "type": "string"
                                },
                                "type": {
                                    "type": "string"
                                },
                                "field": {
                                    "type": "string"
                                }
                            }
                        },
                        "columns": {
                            "type": "object",
                            "dynamic": False,
                            "properties": {
                                "doc_type": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                },
                                "time_ago_interval": {
                                    "type": "float"
                                },
                                "filter_xpath": {
                                    "type": "string"
                                },
                                "field": {
                                    "type": "string"
                                },
                                "late_flag": {
                                    "type": "long"
                                },
                                "format": {
                                    "type": "string"
                                },
                                "enum": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "value": {
                                            "type": "object",
                                            "dynamic": False
                                        },
                                        "key": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "header": {
                                    "type": "object",
                                    "dynamic": False
                                },
                                "model": {
                                    "type": "string"
                                },
                                "advanced": {
                                    "type": "string"
                                }
                            }
                        }
                    }
                },
                "task_list": {
                    "type": "object",
                    "dynamic": False,
                    "properties": {
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "show": {
                            "type": "boolean"
                        },
                        "label": {
                            "type": "object",
                            "dynamic": False
                        }
                    }
                },
                "unique_id": {
                    "type": "string"
                }
            }
        },
        "attribution_notes": {
            "type": "string"
        },
        "admin_password_charset": {
            "type": "string"
        },
        "date_created": {
            "type": "date",
            "format": DATE_FORMATS_STRING
        },
        "cp_is_active": {
            "type": "boolean"
        }
    }
}

APP_INDEX_INFO = ElasticsearchIndexInfo(
    index=APP_INDEX,
    alias=APP_ES_ALIAS,
    type=APP_ES_TYPE,
    mapping=APP_MAPPING,
    hq_index_name=APP_HQ_INDEX_NAME
)
