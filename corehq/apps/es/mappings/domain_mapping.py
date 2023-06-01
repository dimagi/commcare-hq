from corehq.apps.es.client import Tombstone
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING

DOMAIN_MAPPING = {
    "_all": {
        "enabled": False
    },
    "_meta": {
        "comment": "",
        "created": None
    },
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR,
    "dynamic": False,
    "properties": {
        "allow_domain_requests": {
            "type": "boolean"
        },
        "area": {
            "type": "string"
        },
        "attribution_notes": {
            "type": "string"
        },
        "author": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "cached_properties": {
            "dynamic": False,
            "type": "object"
        },
        "call_center_config": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "case_owner_id": {
                    "type": "string"
                },
                "case_type": {
                    "type": "string"
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "enabled": {
                    "type": "boolean"
                },
                "use_fixtures": {
                    "type": "boolean"
                }
            }
        },
        "case_display": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "case_details": {
                    "dynamic": False,
                    "type": "object"
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "form_details": {
                    "dynamic": False,
                    "type": "object"
                }
            }
        },
        "case_sharing": {
            "type": "boolean"
        },
        "cda": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "date": {
                    "format": DATE_FORMATS_STRING,
                    "type": "date"
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "signed": {
                    "type": "boolean"
                },
                "type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "user_id": {
                    "type": "string"
                },
                "user_ip": {
                    "type": "string"
                },
                "version": {
                    "type": "string"
                }
            }
        },
        "commtrack_enabled": {
            "type": "boolean"
        },
        "copy_history": {
            "type": "string"
        },
        "cp_300th_form_submission": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "cp_first_domain_for_user": {
            "type": "boolean"
        },
        "cp_first_form": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "cp_has_app": {
            "type": "boolean"
        },
        "cp_is_active": {
            "type": "boolean"
        },
        "cp_j2me_90_d_bool": {
            "type": "boolean"
        },
        "cp_last_form": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "cp_last_updated": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "cp_n_30_day_cases": {
            "type": "long"
        },
        "cp_n_60_day_cases": {
            "type": "long"
        },
        "cp_n_90_day_cases": {
            "type": "long"
        },
        "cp_n_active_cases": {
            "type": "long"
        },
        "cp_n_active_cc_users": {
            "type": "long"
        },
        "cp_n_cases": {
            "type": "long"
        },
        "cp_n_cc_users": {
            "type": "long"
        },
        "cp_n_forms": {
            "type": "long"
        },
        "cp_n_forms_30_d": {
            "type": "long"
        },
        "cp_n_forms_60_d": {
            "type": "long"
        },
        "cp_n_forms_90_d": {
            "type": "long"
        },
        "cp_n_in_sms": {
            "type": "long"
        },
        "cp_n_inactive_cases": {
            "type": "long"
        },
        "cp_n_j2me_30_d": {
            "type": "long"
        },
        "cp_n_j2me_60_d": {
            "type": "long"
        },
        "cp_n_j2me_90_d": {
            "type": "long"
        },
        "cp_n_out_sms": {
            "type": "long"
        },
        "cp_n_sms_30_d": {
            "type": "long"
        },
        "cp_n_sms_60_d": {
            "type": "long"
        },
        "cp_n_sms_90_d": {
            "type": "long"
        },
        "cp_n_sms_ever": {
            "type": "long"
        },
        "cp_n_sms_in_30_d": {
            "type": "long"
        },
        "cp_n_sms_in_60_d": {
            "type": "long"
        },
        "cp_n_sms_in_90_d": {
            "type": "long"
        },
        "cp_n_sms_out_30_d": {
            "type": "long"
        },
        "cp_n_sms_out_60_d": {
            "type": "long"
        },
        "cp_n_sms_out_90_d": {
            "type": "long"
        },
        "cp_n_users_submitted_form": {
            "type": "long"
        },
        "cp_n_web_users": {
            "type": "long"
        },
        "cp_sms_30_d": {
            "type": "boolean"
        },
        "cp_sms_ever": {
            "type": "boolean"
        },
        "creating_user": {
            "type": "string"
        },
        "date_created": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "default_timezone": {
            "type": "string"
        },
        "deployment": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "city": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "type": "string"
                },
                "countries": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "index": "not_analyzed",
                    "type": "string"
                },
                "description": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "type": "string"
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "public": {
                    "type": "boolean"
                },
                "region": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "type": "string"
                }
            }
        },
        "description": {
            "type": "string"
        },
        "doc_type": {
            "index": "not_analyzed",
            "type": "string"
        },
        "downloads": {
            "type": "long"
        },
        "full_downloads": {
            "type": "long"
        },
        "hipaa_compliant": {
            "type": "boolean"
        },
        "hr_name": {
            "type": "string"
        },
        "internal": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "area": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "type": "string"
                },
                "can_use_data": {
                    "type": "boolean"
                },
                "commcare_edition": {
                    "type": "string"
                },
                "commconnect_domain": {
                    "type": "boolean"
                },
                "commtrack_domain": {
                    "type": "boolean"
                },
                "custom_eula": {
                    "type": "boolean"
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "goal_followup_rate": {
                    "type": "double"
                },
                "goal_time_period": {
                    "type": "long"
                },
                "initiative": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "type": "string"
                },
                "notes": {
                    "type": "string"
                },
                "organization_name": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "type": "string"
                },
                "phone_model": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "type": "string"
                },
                "platform": {
                    "type": "string"
                },
                "project_manager": {
                    "type": "string"
                },
                "project_state": {
                    "type": "string"
                },
                "self_started": {
                    "type": "boolean"
                },
                "sf_account_id": {
                    "type": "string"
                },
                "sf_contract_id": {
                    "type": "string"
                },
                "sub_area": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "type": "string"
                },
                "using_adm": {
                    "type": "boolean"
                },
                "using_call_center": {
                    "type": "boolean"
                },
                "workshop_region": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "type": "string"
                }
            }
        },
        "is_active": {
            "type": "boolean"
        },
        "is_approved": {
            "type": "boolean"
        },
        "is_shared": {
            "type": "boolean"
        },
        "is_sms_billable": {
            "type": "boolean"
        },
        "is_snapshot": {
            "type": "boolean"
        },
        "is_starter_app": {
            "type": "boolean"
        },
        "is_test": {
            "type": "string"
        },
        "last_modified": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "license": {
            "type": "string"
        },
        "migrations": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "has_migrated_permissions": {
                    "type": "boolean"
                }
            }
        },
        "multimedia_included": {
            "type": "boolean"
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
        "organization": {
            "type": "string"
        },
        "phone_model": {
            "type": "string"
        },
        "project_type": {
            "analyzer": "comma",
            "type": "string"
        },
        "published": {
            "type": "boolean"
        },
        "publisher": {
            "type": "string"
        },
        "restrict_superusers": {
            "type": "boolean"
        },
        "secure_submissions": {
            "type": "boolean"
        },
        "short_description": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "sms_case_registration_enabled": {
            "type": "boolean"
        },
        "sms_case_registration_owner_id": {
            "type": "string"
        },
        "sms_case_registration_type": {
            "type": "string"
        },
        "sms_case_registration_user_id": {
            "type": "string"
        },
        "sms_mobile_worker_registration_enabled": {
            "type": "boolean"
        },
        "snapshot_head": {
            "type": "boolean"
        },
        "snapshot_time": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "sub_area": {
            "type": "string"
        },
        "subscription": {
            "type": "string"
        },
        "survey_management_enabled": {
            "type": "boolean"
        },
        "tags": {
            "type": "string"
        },
        "title": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "use_sql_backend": {
            "type": "boolean"
        },
        "yt_id": {
            "type": "string"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}
