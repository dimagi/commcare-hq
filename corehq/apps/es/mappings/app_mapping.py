from corehq.apps.es.client import Tombstone
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING

APP_MAPPING = {
    "_all": {
        "enabled": False
    },
    "_meta": {
        "created": None
    },
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR,
    "dynamic": False,
    "properties": {
        "@indexed_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "admin_password": {
            "type": "string"
        },
        "admin_password_charset": {
            "type": "string"
        },
        "application_version": {
            "type": "string"
        },
        "attribution_notes": {
            "type": "string"
        },
        "build_broken": {
            "type": "boolean"
        },
        "build_comment": {
            "type": "string"
        },
        "build_langs": {
            "index": "not_analyzed",
            "type": "string"
        },
        "build_signed": {
            "type": "boolean"
        },
        "build_spec": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "build_number": {
                    "type": "long"
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "latest": {
                    "type": "boolean"
                },
                "version": {
                    "type": "string"
                }
            }
        },
        "built_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "built_with": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "build_number": {
                    "type": "long"
                },
                "datetime": {
                    "format": DATE_FORMATS_STRING,
                    "type": "date"
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "latest": {
                    "type": "boolean"
                },
                "signed": {
                    "type": "boolean"
                },
                "version": {
                    "type": "string"
                }
            }
        },
        "cached_properties": {
            "dynamic": False,
            "type": "object"
        },
        "case_sharing": {
            "type": "boolean"
        },
        "cloudcare_enabled": {
            "type": "boolean"
        },
        "comment_from": {
            "type": "string"
        },
        "copy_history": {
            "type": "string"
        },
        "copy_of": {
            "index": "not_analyzed",
            "type": "string"
        },
        "cp_is_active": {
            "type": "boolean"
        },
        "created_from_template": {
            "type": "string"
        },
        "date_created": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "deployment_date": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "description": {
            "type": "string"
        },
        "doc_type": {
            "index": "not_analyzed",
            "type": "string"
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
        "family_id": {
            "type": "string"
        },
        "force_http": {
            "type": "boolean"
        },
        "is_released": {
            "type": "boolean"
        },
        "langs": {
            "index": "not_analyzed",
            "type": "string"
        },
        "modules": {
            "dynamic": False,
            "type": "nested",
            "properties": {
                "case_list": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "label": {
                            "dynamic": False,
                            "type": "object"
                        },
                        "show": {
                            "type": "boolean"
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
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "columns": {
                            "dynamic": False,
                            "type": "object",
                            "properties": {
                                "advanced": {
                                    "type": "string"
                                },
                                "doc_type": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                },
                                "enum": {
                                    "dynamic": False,
                                    "type": "object",
                                    "properties": {
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "key": {
                                            "type": "string"
                                        },
                                        "value": {
                                            "dynamic": False,
                                            "type": "object"
                                        }
                                    }
                                },
                                "field": {
                                    "type": "string"
                                },
                                "filter_xpath": {
                                    "type": "string"
                                },
                                "format": {
                                    "type": "string"
                                },
                                "header": {
                                    "dynamic": False,
                                    "type": "object"
                                },
                                "late_flag": {
                                    "type": "long"
                                },
                                "model": {
                                    "type": "string"
                                },
                                "time_ago_interval": {
                                    "type": "float"
                                }
                            }
                        },
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "filter": {
                            "type": "string"
                        },
                        "sort_elements": {
                            "dynamic": False,
                            "type": "object",
                            "properties": {
                                "direction": {
                                    "type": "string"
                                },
                                "doc_type": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                },
                                "field": {
                                    "type": "string"
                                },
                                "type": {
                                    "type": "string"
                                }
                            }
                        },
                        "type": {
                            "type": "string"
                        }
                    }
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "forms": {
                    "dynamic": False,
                    "type": "nested",
                    "properties": {
                        "actions": {
                            "dynamic": False,
                            "type": "object",
                            "properties": {
                                "case_preload": {
                                    "dynamic": False,
                                    "type": "object",
                                    "properties": {
                                        "condition": {
                                            "dynamic": False,
                                            "type": "object",
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
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "preload": {
                                            "dynamic": False,
                                            "type": "object"
                                        }
                                    }
                                },
                                "close_case": {
                                    "dynamic": False,
                                    "type": "object",
                                    "properties": {
                                        "condition": {
                                            "dynamic": False,
                                            "type": "object",
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
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        }
                                    }
                                },
                                "close_referral": {
                                    "dynamic": False,
                                    "type": "object",
                                    "properties": {
                                        "condition": {
                                            "dynamic": False,
                                            "type": "object",
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
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        }
                                    }
                                },
                                "doc_type": {
                                    "index": "not_analyzed",
                                    "type": "string"
                                },
                                "load_from_form": {
                                    "dynamic": False,
                                    "type": "object",
                                    "properties": {
                                        "condition": {
                                            "dynamic": False,
                                            "type": "object",
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
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "preload": {
                                            "dynamic": False,
                                            "type": "object"
                                        }
                                    }
                                },
                                "open_case": {
                                    "dynamic": False,
                                    "type": "object",
                                    "properties": {
                                        "condition": {
                                            "dynamic": False,
                                            "type": "object",
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
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "external_id": {
                                            "type": "string"
                                        },
                                        "name_path": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "open_referral": {
                                    "dynamic": False,
                                    "type": "object",
                                    "properties": {
                                        "condition": {
                                            "dynamic": False,
                                            "type": "object",
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
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "followup_date": {
                                            "type": "string"
                                        },
                                        "name_path": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "referral_preload": {
                                    "dynamic": False,
                                    "type": "object",
                                    "properties": {
                                        "condition": {
                                            "dynamic": False,
                                            "type": "object",
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
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "preload": {
                                            "dynamic": False,
                                            "type": "object"
                                        }
                                    }
                                },
                                "subcases": {
                                    "dynamic": False,
                                    "type": "nested",
                                    "properties": {
                                        "case_name": {
                                            "type": "string"
                                        },
                                        "case_properties": {
                                            "dynamic": False,
                                            "type": "object"
                                        },
                                        "case_type": {
                                            "type": "string"
                                        },
                                        "condition": {
                                            "dynamic": False,
                                            "type": "object",
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
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "reference_id": {
                                            "type": "string"
                                        },
                                        "repeat_context": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "update_case": {
                                    "dynamic": False,
                                    "type": "object",
                                    "properties": {
                                        "condition": {
                                            "dynamic": False,
                                            "type": "object",
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
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "update": {
                                            "dynamic": False,
                                            "type": "object"
                                        }
                                    }
                                },
                                "update_referral": {
                                    "dynamic": False,
                                    "type": "object",
                                    "properties": {
                                        "condition": {
                                            "dynamic": False,
                                            "type": "object",
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
                                        },
                                        "doc_type": {
                                            "index": "not_analyzed",
                                            "type": "string"
                                        },
                                        "followup_date": {
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
                        "form_filter": {
                            "type": "string"
                        },
                        "form_type": {
                            "type": "string"
                        },
                        "name": {
                            "dynamic": False,
                            "type": "object"
                        },
                        "requires": {
                            "type": "string"
                        },
                        "show_count": {
                            "type": "boolean"
                        },
                        "unique_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "version": {
                            "type": "long"
                        },
                        "xmlns": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    }
                },
                "name": {
                    "dynamic": False,
                    "type": "object"
                },
                "parent_select": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "active": {
                            "type": "boolean"
                        },
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "module_id": {
                            "type": "string"
                        },
                        "relationship": {
                            "type": "string"
                        }
                    }
                },
                "put_in_root": {
                    "type": "boolean"
                },
                "referral_list": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "label": {
                            "dynamic": False,
                            "type": "object"
                        },
                        "show": {
                            "type": "boolean"
                        }
                    }
                },
                "root_module_id": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "task_list": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "label": {
                            "dynamic": False,
                            "type": "object"
                        },
                        "show": {
                            "type": "boolean"
                        }
                    }
                },
                "unique_id": {
                    "type": "string"
                }
            }
        },
        "multimedia_map": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "media_type": {
                    "type": "string"
                },
                "multimedia_id": {
                    "type": "string"
                },
                "unique_id": {
                    "type": "string"
                },
                "version": {
                    "type": "long"
                }
            }
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
        "phone_model": {
            "type": "string"
        },
        "platform": {
            "type": "string"
        },
        "profile": {
            "dynamic": True,
            "type": "object"
        },
        "recipients": {
            "type": "string"
        },
        "secure_submissions": {
            "type": "boolean"
        },
        "short_odk_media_url": {
            "index": "not_analyzed",
            "type": "string"
        },
        "short_odk_url": {
            "index": "not_analyzed",
            "type": "string"
        },
        "short_url": {
            "index": "not_analyzed",
            "type": "string"
        },
        "success_message": {
            "dynamic": False,
            "type": "object"
        },
        "text_input": {
            "type": "string"
        },
        "translation_strategy": {
            "type": "string"
        },
        "translations": {
            "dynamic": False,
            "type": "object"
        },
        "upstream_app_id": {
            "type": "string"
        },
        "upstream_version": {
            "type": "long"
        },
        "use_custom_suite": {
            "type": "boolean"
        },
        "user_type": {
            "type": "string"
        },
        "vellum_case_management": {
            "type": "boolean"
        },
        "version": {
            "type": "long"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}
