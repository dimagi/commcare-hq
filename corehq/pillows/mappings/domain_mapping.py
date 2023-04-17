from pillowtop.es_utils import DOMAIN_HQ_INDEX_NAME, ElasticsearchIndexInfo

from corehq.apps.es.client import Tombstone
from corehq.apps.es.domains import domain_adapter
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.util.elastic import prefix_for_tests

DOMAIN_INDEX = domain_adapter.index_name
DOMAIN_ES_ALIAS = prefix_for_tests('hqdomains')

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
            "type": "text"
        },
        "attribution_notes": {
            "type": "text"
        },
        "author": {
            "fields": {
                "author": {
                    "type": "text"
                },
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "multi_field"
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
                    "type": "text"
                },
                "case_type": {
                    "type": "text"
                },
                "doc_type": {
                    "type": "keyword"
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
                    "type": "keyword"
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
                    "type": "keyword"
                },
                "signed": {
                    "type": "boolean"
                },
                "type": {
                    "type": "keyword"
                },
                "user_id": {
                    "type": "text"
                },
                "user_ip": {
                    "type": "text"
                },
                "version": {
                    "type": "text"
                }
            }
        },
        "commtrack_enabled": {
            "type": "boolean"
        },
        "copy_history": {
            "type": "text"
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
            "type": "text"
        },
        "date_created": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "default_timezone": {
            "type": "text"
        },
        "deployment": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "city": {
                    "fields": {
                        "city": {
                            "type": "text"
                        },
                        "exact": {
                            "type": "keyword"
                        }
                    },
                    "type": "multi_field"
                },
                "countries": {
                    "fields": {
                        "countries": {
                            "type": "keyword"
                        },
                        "exact": {
                            "type": "keyword"
                        }
                    },
                    "type": "multi_field"
                },
                "description": {
                    "fields": {
                        "description": {
                            "type": "text"
                        },
                        "exact": {
                            "type": "keyword"
                        }
                    },
                    "type": "multi_field"
                },
                "doc_type": {
                    "type": "keyword"
                },
                "public": {
                    "type": "boolean"
                },
                "region": {
                    "fields": {
                        "exact": {
                            "type": "keyword"
                        },
                        "region": {
                            "type": "text"
                        }
                    },
                    "type": "multi_field"
                }
            }
        },
        "description": {
            "type": "text"
        },
        "doc_type": {
            "type": "keyword"
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
            "type": "text"
        },
        "internal": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "area": {
                    "fields": {
                        "area": {
                            "type": "text"
                        },
                        "exact": {
                            "type": "keyword"
                        }
                    },
                    "type": "multi_field"
                },
                "can_use_data": {
                    "type": "boolean"
                },
                "commcare_edition": {
                    "type": "text"
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
                    "type": "keyword"
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
                            "type": "keyword"
                        },
                        "initiative": {
                            "type": "text"
                        }
                    },
                    "type": "multi_field"
                },
                "notes": {
                    "type": "text"
                },
                "organization_name": {
                    "fields": {
                        "exact": {
                            "type": "keyword"
                        },
                        "organization_name": {
                            "type": "text"
                        }
                    },
                    "type": "multi_field"
                },
                "phone_model": {
                    "fields": {
                        "exact": {
                            "type": "keyword"
                        },
                        "phone_model": {
                            "type": "text"
                        }
                    },
                    "type": "multi_field"
                },
                "platform": {
                    "type": "text"
                },
                "project_manager": {
                    "type": "text"
                },
                "project_state": {
                    "type": "text"
                },
                "self_started": {
                    "type": "boolean"
                },
                "sf_account_id": {
                    "type": "text"
                },
                "sf_contract_id": {
                    "type": "text"
                },
                "sub_area": {
                    "fields": {
                        "exact": {
                            "type": "keyword"
                        },
                        "sub_area": {
                            "type": "text"
                        }
                    },
                    "type": "multi_field"
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
                            "type": "keyword"
                        },
                        "workshop_region": {
                            "type": "text"
                        }
                    },
                    "type": "multi_field"
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
            "type": "text"
        },
        "last_modified": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "license": {
            "type": "text"
        },
        "migrations": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "doc_type": {
                    "type": "keyword"
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
                    "type": "keyword"
                },
                "name": {
                    "type": "text"
                }
            },
            "type": "multi_field"
        },
        "organization": {
            "type": "text"
        },
        "phone_model": {
            "type": "text"
        },
        "project_type": {
            "analyzer": "comma",
            "type": "text"
        },
        "published": {
            "type": "boolean"
        },
        "publisher": {
            "type": "text"
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
                    "type": "keyword"
                },
                "short_description": {
                    "type": "text"
                }
            },
            "type": "multi_field"
        },
        "sms_case_registration_enabled": {
            "type": "boolean"
        },
        "sms_case_registration_owner_id": {
            "type": "text"
        },
        "sms_case_registration_type": {
            "type": "text"
        },
        "sms_case_registration_user_id": {
            "type": "text"
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
            "type": "text"
        },
        "subscription": {
            "type": "text"
        },
        "survey_management_enabled": {
            "type": "boolean"
        },
        "tags": {
            "type": "text"
        },
        "title": {
            "fields": {
                "exact": {
                    "type": "keyword"
                },
                "title": {
                    "type": "text"
                }
            },
            "type": "multi_field"
        },
        "use_sql_backend": {
            "type": "boolean"
        },
        "yt_id": {
            "type": "text"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}


DOMAIN_INDEX_INFO = ElasticsearchIndexInfo(
    index=DOMAIN_INDEX,
    alias=DOMAIN_ES_ALIAS,
    type=domain_adapter.type,
    mapping=DOMAIN_MAPPING,
    hq_index_name=DOMAIN_HQ_INDEX_NAME
)
