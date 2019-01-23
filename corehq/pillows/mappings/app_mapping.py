from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.elastic import es_index
from pillowtop.es_utils import ElasticsearchIndexInfo

APP_INDEX = es_index("hqapps_2019-01-23")
APP_MAPPING = {
    "date_formats": [
        "yyyy-MM-dd",
        "yyyy-MM-dd'T'HH:mm:ssZZ",
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'",
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        "yyyy-MM-dd'T'HH:mm:ssZ",
        "yyyy-MM-dd'T'HH:mm:ssZZ'Z'",
        "yyyy-MM-dd'T'HH:mm:ss.SSSZZ",
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd' 'HH:mm:ss",
        "yyyy-MM-dd' 'HH:mm:ss.SSSSSS",
        "mm/dd/yy' 'HH:mm:ss"
    ],
    "dynamic": False,
    "_meta": {"created": None},
    "date_detection": False,
    "properties": {
        "short_url": {"type": "string"},
        "build_broken": {"type": "boolean"},
        "copy_of": {"type": "string"},
        "phone_model": {"type": "string"},
        "copy_history": {"type": "string"},
        "is_released": {"type": "boolean"},
        "platform": {"type": "string"},
        "admin_password": {"type": "string"},
        "build_spec": {
            "type": "object",
            "dynamic": False,
            "properties": {
                "doc_type": {"index": "not_analyzed", "type": "string"},
                "version": {"type": "string"},
                "build_number": {"type": "long"},
                "latest": {"type": "boolean"}
            }
        },
        "success_message": {"type": "object", "dynamic": False},
        "multimedia_map": {
            "type": "object",
            "dynamic": False,
            "properties": {
                "doc_type": {"index": "not_analyzed", "type": "string"},
                "output_size": {"type": "object", "dynamic": False},
                "version": {"type": "long"},
                "multimedia_id": {"type": "string"},
                "media_type": {"type": "string"},
                "unique_id": {"type": "string"}
            }
        },
        "comment_from": {"type": "string"},
        "cloudcare_enabled": {"type": "boolean"},
        "recipients": {"type": "string"},
        "translations": {"type": "object", "dynamic": False},
        "built_on": {
            "type": "date",
            "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"
        },
        "built_with": {
            "type": "object",
            "dynamic": False,
            "properties": {
                "doc_type": {"index": "not_analyzed", "type": "string"},
                "build_number": {"type": "long"},
                "signed": {"type": "boolean"},
                "datetime": {
                    "type": "date",
                    "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"
                },
                "version": {"type": "string"},
                "latest": {"type": "boolean"}
            }
        },
        "application_version": {"type": "string"},
        "build_comment": {"type": "string"},
        "doc_type": {"index": "not_analyzed", "type": "string"},
        "name": {
            "fields": {
                "exact": {"index": "not_analyzed", "type": "string"},
                "name": {"index": "analyzed", "type": "string"}
            },
            "type": "multi_field"
        },
        "force_http": {"type": "boolean"},
        "created_from_template": {"type": "string"},
        "translation_strategy": {"type": "string"},
        "case_sharing": {"type": "boolean"},
        "short_odk_url": {"type": "string"},
        "domain": {
            "fields": {
                "domain": {"index": "analyzed", "type": "string"},
                "exact": {"index": "not_analyzed", "type": "string"}
            },
            "type": "multi_field"
        },
        "build_langs": {"type": "string"},
        "deployment_date": {
            "type": "date",
            "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"
        },
        "user_type": {"type": "string"},
        "text_input": {"type": "string"},
        "secure_submissions": {"type": "boolean"},
        "build_signed": {"type": "boolean"},
        "vellum_case_management": {"type": "boolean"},
        "version": {"type": "long"},
        "profile": {"type": "object", "dynamic": True},
        "description": {"type": "string"},
        "short_odk_media_url": {"type": "string"},
        "langs": {"type": "string"},
        "use_custom_suite": {"type": "boolean"},
        "cached_properties": {"type": "object", "dynamic": False},
        "modules": {
            "type": "nested",
            "dynamic": False,
            "properties": {
                "case_list": {
                    "type": "object",
                    "dynamic": False,
                    "properties": {
                        "doc_type": {"index": "not_analyzed", "type": "string"},
                        "show": {"type": "boolean"},
                        "label": {"type": "object", "dynamic": False}
                    }
                },
                "put_in_root": {"type": "boolean"},
                "root_module_id": {"index": "not_analyzed", "type": "string"},
                "doc_type": {"index": "not_analyzed", "type": "string"},
                "name": {"type": "object", "dynamic": False},
                "referral_list": {
                    "type": "object",
                    "dynamic": False,
                    "properties": {
                        "doc_type": {"index": "not_analyzed", "type": "string"},
                        "show": {"type": "boolean"},
                        "label": {"type": "object", "dynamic": False}
                    }
                },
                "parent_select": {
                    "type": "object",
                    "dynamic": False,
                    "properties": {
                        "active": {"type": "boolean"},
                        "doc_type": {"index": "not_analyzed", "type": "string"},
                        "relationship": {"type": "string"},
                        "module_id": {"type": "string"}
                    }
                },
                "forms": {
                    "type": "nested",
                    "dynamic": False,
                    "properties": {
                        "unique_id": {"type": "string"},
                        "doc_type": {"index": "not_analyzed", "type": "string"},
                        "version": {"type": "long"},
                        "name": {"type": "object", "dynamic": False},
                        "show_count": {"type": "boolean"},
                        "form_type": {"type": "string"},
                        "requires": {"type": "string"},
                        "form_filter": {"type": "string"},
                        "actions": {
                            "type": "object",
                            "dynamic": False,
                            "properties": {
                                "subcases": {
                                    "type": "nested",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {"index": "not_analyzed", "type": "string"},
                                        "repeat_context": {"type": "string"},
                                        "case_properties": {"type": "object", "dynamic": False},
                                        "case_type": {"type": "string"},
                                        "reference_id": {"type": "string"},
                                        "case_name": {"type": "string"},
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {"type": "string"},
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {"type": "string"},
                                                "type": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "update_case": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {"index": "not_analyzed", "type": "string"},
                                        "update": {"type": "object", "dynamic": False},
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {"type": "string"},
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {"type": "string"},
                                                "type": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "close_referral": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {"index": "not_analyzed", "type": "string"},
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {"type": "string"},
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {"type": "string"},
                                                "type": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "open_referral": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "name_path": {"type": "string"},
                                        "doc_type": {"index": "not_analyzed", "type": "string"},
                                        "followup_date": {"type": "string"},
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {"type": "string"},
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {"type": "string"},
                                                "type": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "case_preload": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "preload": {"type": "object", "dynamic": False},
                                        "doc_type": {"index": "not_analyzed", "type": "string"},
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {"type": "string"},
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {"type": "string"},
                                                "type": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "doc_type": {"index": "not_analyzed", "type": "string"},
                                "load_from_form": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "preload": {"type": "object", "dynamic": False},
                                        "doc_type": {"index": "not_analyzed", "type": "string"},
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {"type": "string"},
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {"type": "string"},
                                                "type": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "open_case": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "name_path": {"type": "string"},
                                        "doc_type": {"index": "not_analyzed", "type": "string"},
                                        "external_id": {"type": "string"},
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {"type": "string"},
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {"type": "string"},
                                                "type": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "update_referral": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {"index": "not_analyzed", "type": "string"},
                                        "followup_date": {"type": "string"},
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {"type": "string"},
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {"type": "string"},
                                                "type": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "referral_preload": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "preload": {"type": "object", "dynamic": False},
                                        "doc_type": {"index": "not_analyzed", "type": "string"},
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {"type": "string"},
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {"type": "string"},
                                                "type": {"type": "string"}
                                            }
                                        }
                                    }
                                },
                                "close_case": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {"index": "not_analyzed", "type": "string"},
                                        "condition": {
                                            "type": "object",
                                            "dynamic": False,
                                            "properties": {
                                                "answer": {"type": "string"},
                                                "doc_type": {
                                                    "index": "not_analyzed",
                                                    "type": "string"
                                                },
                                                "question": {"type": "string"},
                                                "type": {"type": "string"}
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "xmlns": {"type": "string"}
                    }
                },
                "case_type": {
                    "fields": {
                        "case_type": {"index": "analyzed", "type": "string"},
                        "exact": {"index": "not_analyzed", "type": "string"}
                    },
                    "type": "multi_field"
                },
                "details": {
                    "type": "object",
                    "dynamic": False,
                    "properties": {
                        "filter": {"type": "string"},
                        "doc_type": {"index": "not_analyzed", "type": "string"},
                        "type": {"type": "string"},
                        "sort_elements": {
                            "type": "object",
                            "dynamic": False,
                            "properties": {
                                "doc_type": {"index": "not_analyzed", "type": "string"},
                                "direction": {"type": "string"},
                                "type": {"type": "string"},
                                "field": {"type": "string"}
                            }
                        },
                        "columns": {
                            "type": "object",
                            "dynamic": False,
                            "properties": {
                                "doc_type": {"index": "not_analyzed", "type": "string"},
                                "time_ago_interval": {"type": "float"},
                                "filter_xpath": {"type": "string"},
                                "field": {"type": "string"},
                                "late_flag": {"type": "long"},
                                "format": {"type": "string"},
                                "enum": {
                                    "type": "object",
                                    "dynamic": False,
                                    "properties": {
                                        "doc_type": {"index": "not_analyzed", "type": "string"},
                                        "value": {"type": "object", "dynamic": False},
                                        "key": {"type": "string"}
                                    }
                                },
                                "header": {"type": "object", "dynamic": False},
                                "model": {"type": "string"},
                                "advanced": {"type": "string"}
                            }
                        }
                    }
                },
                "task_list": {
                    "type": "object",
                    "dynamic": False,
                    "properties": {
                        "doc_type": {"index": "not_analyzed", "type": "string"},
                        "show": {"type": "boolean"},
                        "label": {"type": "object", "dynamic": False}
                    }
                },
                "unique_id": {"type": "string"}
            }
        },
        "attribution_notes": {"type": "string"},
        "admin_password_charset": {"type": "string"},
        "date_created": {
            "type": "date",
            "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss"
        },
        "cp_is_active": {"type": "boolean"}
    }
}

APP_ES_ALIAS = "hqapps"
APP_ES_TYPE = "app"
APP_INDEX_INFO = ElasticsearchIndexInfo(
    index=APP_INDEX,
    alias=APP_ES_ALIAS,
    type=APP_ES_TYPE,
    mapping=APP_MAPPING
)
