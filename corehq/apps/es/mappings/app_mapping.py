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
            "type": "text"
        },
        "admin_password_charset": {
            "type": "text"
        },
        "application_version": {
            "type": "text"
        },
        "attribution_notes": {
            "type": "text"
        },
        "build_broken": {
            "type": "boolean"
        },
        "build_comment": {
            "type": "text"
        },
        "build_langs": {
            "type": "keyword"
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
                    "type": "keyword"
                },
                "latest": {
                    "type": "boolean"
                },
                "version": {
                    "type": "text"
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
                    "type": "keyword"
                },
                "latest": {
                    "type": "boolean"
                },
                "signed": {
                    "type": "boolean"
                },
                "version": {
                    "type": "text"
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
            "type": "text"
        },
        "copy_history": {
            "type": "text"
        },
        "copy_of": {
            "type": "keyword"
        },
        "cp_is_active": {
            "type": "boolean"
        },
        "created_from_template": {
            "type": "text"
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
            "type": "text"
        },
        "doc_id": {
            "type": "keyword"
        },
        "doc_type": {
            "type": "keyword"
        },
        "domain": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        "family_id": {
            "type": "keyword"
        },
        "force_http": {
            "type": "boolean"
        },
        "is_released": {
            "type": "boolean"
        },
        "langs": {
            "type": "keyword"
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
                            "type": "keyword"
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
                            "type": "keyword"
                        }
                    },
                    "type": "text"
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
                                    "type": "text"
                                },
                                "doc_type": {
                                    "type": "keyword"
                                },
                                "enum": {
                                    "dynamic": False,
                                    "type": "object",
                                    "properties": {
                                        "doc_type": {
                                            "type": "keyword"
                                        },
                                        "key": {
                                            "type": "text"
                                        },
                                        "value": {
                                            "dynamic": False,
                                            "type": "object"
                                        }
                                    }
                                },
                                "field": {
                                    "type": "text"
                                },
                                "filter_xpath": {
                                    "type": "text"
                                },
                                "format": {
                                    "type": "text"
                                },
                                "header": {
                                    "dynamic": False,
                                    "type": "object"
                                },
                                "late_flag": {
                                    "type": "long"
                                },
                                "model": {
                                    "type": "text"
                                },
                                "time_ago_interval": {
                                    "type": "float"
                                }
                            }
                        },
                        "doc_type": {
                            "type": "keyword"
                        },
                        "filter": {
                            "type": "text"
                        },
                        "sort_elements": {
                            "dynamic": False,
                            "type": "object",
                            "properties": {
                                "direction": {
                                    "type": "text"
                                },
                                "doc_type": {
                                    "type": "keyword"
                                },
                                "field": {
                                    "type": "text"
                                },
                                "type": {
                                    "type": "text"
                                }
                            }
                        },
                        "type": {
                            "type": "text"
                        }
                    }
                },
                "doc_type": {
                    "type": "keyword"
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
                                                    "type": "text"
                                                },
                                                "doc_type": {
                                                    "type": "keyword"
                                                },
                                                "question": {
                                                    "type": "text"
                                                },
                                                "type": {
                                                    "type": "text"
                                                }
                                            }
                                        },
                                        "doc_type": {
                                            "type": "keyword"
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
                                                    "type": "text"
                                                },
                                                "doc_type": {
                                                    "type": "keyword"
                                                },
                                                "question": {
                                                    "type": "text"
                                                },
                                                "type": {
                                                    "type": "text"
                                                }
                                            }
                                        },
                                        "doc_type": {
                                            "type": "keyword"
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
                                                    "type": "text"
                                                },
                                                "doc_type": {
                                                    "type": "keyword"
                                                },
                                                "question": {
                                                    "type": "text"
                                                },
                                                "type": {
                                                    "type": "text"
                                                }
                                            }
                                        },
                                        "doc_type": {
                                            "type": "keyword"
                                        }
                                    }
                                },
                                "doc_type": {
                                    "type": "keyword"
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
                                                    "type": "text"
                                                },
                                                "doc_type": {
                                                    "type": "keyword"
                                                },
                                                "question": {
                                                    "type": "text"
                                                },
                                                "type": {
                                                    "type": "text"
                                                }
                                            }
                                        },
                                        "doc_type": {
                                            "type": "keyword"
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
                                                    "type": "text"
                                                },
                                                "doc_type": {
                                                    "type": "keyword"
                                                },
                                                "question": {
                                                    "type": "text"
                                                },
                                                "type": {
                                                    "type": "text"
                                                }
                                            }
                                        },
                                        "doc_type": {
                                            "type": "keyword"
                                        },
                                        "external_id": {
                                            "type": "keyword"
                                        },
                                        "name_path": {
                                            "type": "text"
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
                                                    "type": "text"
                                                },
                                                "doc_type": {
                                                    "type": "keyword"
                                                },
                                                "question": {
                                                    "type": "text"
                                                },
                                                "type": {
                                                    "type": "text"
                                                }
                                            }
                                        },
                                        "doc_type": {
                                            "type": "keyword"
                                        },
                                        "followup_date": {
                                            "type": "text"
                                        },
                                        "name_path": {
                                            "type": "text"
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
                                                    "type": "text"
                                                },
                                                "doc_type": {
                                                    "type": "keyword"
                                                },
                                                "question": {
                                                    "type": "text"
                                                },
                                                "type": {
                                                    "type": "text"
                                                }
                                            }
                                        },
                                        "doc_type": {
                                            "type": "keyword"
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
                                            "type": "text"
                                        },
                                        "case_properties": {
                                            "dynamic": False,
                                            "type": "object"
                                        },
                                        "case_type": {
                                            "type": "text"
                                        },
                                        "condition": {
                                            "dynamic": False,
                                            "type": "object",
                                            "properties": {
                                                "answer": {
                                                    "type": "text"
                                                },
                                                "doc_type": {
                                                    "type": "keyword"
                                                },
                                                "question": {
                                                    "type": "text"
                                                },
                                                "type": {
                                                    "type": "text"
                                                }
                                            }
                                        },
                                        "doc_type": {
                                            "type": "keyword"
                                        },
                                        "reference_id": {
                                            "type": "keyword"
                                        },
                                        "repeat_context": {
                                            "type": "text"
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
                                                    "type": "text"
                                                },
                                                "doc_type": {
                                                    "type": "keyword"
                                                },
                                                "question": {
                                                    "type": "text"
                                                },
                                                "type": {
                                                    "type": "text"
                                                }
                                            }
                                        },
                                        "doc_type": {
                                            "type": "keyword"
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
                                                    "type": "text"
                                                },
                                                "doc_type": {
                                                    "type": "keyword"
                                                },
                                                "question": {
                                                    "type": "text"
                                                },
                                                "type": {
                                                    "type": "text"
                                                }
                                            }
                                        },
                                        "doc_type": {
                                            "type": "keyword"
                                        },
                                        "followup_date": {
                                            "type": "text"
                                        }
                                    }
                                }
                            }
                        },
                        "doc_type": {
                            "type": "keyword"
                        },
                        "form_filter": {
                            "type": "text"
                        },
                        "form_type": {
                            "type": "text"
                        },
                        "name": {
                            "dynamic": False,
                            "type": "object"
                        },
                        "requires": {
                            "type": "text"
                        },
                        "show_count": {
                            "type": "boolean"
                        },
                        "unique_id": {
                            "type": "keyword"
                        },
                        "version": {
                            "type": "long"
                        },
                        "xmlns": {
                            "type": "keyword"
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
                            "type": "keyword"
                        },
                        "module_id": {
                            "type": "keyword"
                        },
                        "relationship": {
                            "type": "text"
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
                            "type": "keyword"
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
                    "type": "keyword"
                },
                "task_list": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "doc_type": {
                            "type": "keyword"
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
                    "type": "keyword"
                }
            }
        },
        "multimedia_map": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "doc_type": {
                    "type": "keyword"
                },
                "media_type": {
                    "type": "text"
                },
                "multimedia_id": {
                    "type": "keyword"
                },
                "unique_id": {
                    "type": "keyword"
                },
                "version": {
                    "type": "long"
                }
            }
        },
        "name": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        "phone_model": {
            "type": "text"
        },
        "platform": {
            "type": "text"
        },
        "profile": {
            "dynamic": True,
            "type": "object"
        },
        "recipients": {
            "type": "text"
        },
        "secure_submissions": {
            "type": "boolean"
        },
        "short_odk_media_url": {
            "type": "keyword"
        },
        "short_odk_url": {
            "type": "keyword"
        },
        "short_url": {
            "type": "keyword"
        },
        "success_message": {
            "dynamic": False,
            "type": "object"
        },
        "text_input": {
            "type": "text"
        },
        "translation_strategy": {
            "type": "text"
        },
        "translations": {
            "dynamic": False,
            "type": "object"
        },
        "upstream_app_id": {
            "type": "keyword"
        },
        "upstream_version": {
            "type": "long"
        },
        "use_custom_suite": {
            "type": "boolean"
        },
        "user_type": {
            "type": "text"
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
