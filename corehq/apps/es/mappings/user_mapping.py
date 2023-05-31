from corehq.apps.es.client import Tombstone
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING

USER_MAPPING = {
    "_all": {
        "analyzer": "standard"
    },
    "_meta": {
        "created": None
    },
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR,
    "dynamic": False,
    "properties": {
        "CURRENT_VERSION": {
            "type": "string"
        },
        "__group_ids": {
            "type": "string"
        },
        "__group_names": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "analytics_enabled": {
            "type": "boolean"
        },
        "assigned_location_ids": {
            "type": "string"
        },
        "base_doc": {
            "type": "string"
        },
        "base_username": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "created_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "date_joined": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "devices": {
            "dynamic": False,
            "type": "nested",
            "properties": {
                "app_meta": {
                    "dynamic": False,
                    "type": "nested",
                    "properties": {
                        "app_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "build_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "build_version": {
                            "type": "integer"
                        },
                        "last_heartbeat": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "last_request": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "last_submission": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "last_sync": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "num_quarantined_forms": {
                            "type": "integer"
                        },
                        "num_unsent_forms": {
                            "type": "integer"
                        }
                    }
                },
                "commcare_version": {
                    "type": "string"
                },
                "device_id": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "last_used": {
                    "format": DATE_FORMATS_STRING,
                    "type": "date"
                }
            }
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
        "domain_membership": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "assigned_location_ids": {
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
                "is_admin": {
                    "type": "boolean"
                },
                "location_id": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "override_global_tz": {
                    "type": "boolean"
                },
                "role_id": {
                    "type": "string"
                },
                "timezone": {
                    "type": "string"
                }
            }
        },
        "domain_memberships": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "assigned_location_ids": {
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
                "is_admin": {
                    "type": "boolean"
                },
                "location_id": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "override_global_tz": {
                    "type": "boolean"
                },
                "role_id": {
                    "type": "string"
                },
                "timezone": {
                    "type": "string"
                }
            }
        },
        "eulas": {
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
        "first_name": {
            "type": "string"
        },
        "is_active": {
            "type": "boolean"
        },
        "is_demo_user": {
            "type": "boolean"
        },
        "is_staff": {
            "type": "boolean"
        },
        "is_superuser": {
            "type": "boolean"
        },
        "language": {
            "type": "string"
        },
        "last_device": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "app_meta": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "app_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "build_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "build_version": {
                            "type": "integer"
                        },
                        "last_heartbeat": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "last_request": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "last_submission": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "last_sync": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "num_quarantined_forms": {
                            "type": "integer"
                        },
                        "num_unsent_forms": {
                            "type": "integer"
                        }
                    }
                },
                "commcare_version": {
                    "type": "string"
                },
                "device_id": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "last_used": {
                    "format": DATE_FORMATS_STRING,
                    "type": "date"
                }
            }
        },
        "last_login": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "last_name": {
            "type": "string"
        },
        "location_id": {
            "index": "not_analyzed",
            "type": "string"
        },
        "password": {
            "type": "string"
        },
        "phone_numbers": {
            "type": "string"
        },
        "registering_device_id": {
            "type": "string"
        },
        "reporting_metadata": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "last_build_for_user": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "app_id": {
                            "type": "string"
                        },
                        "build_version": {
                            "type": "integer"
                        },
                        "build_version_date": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        }
                    }
                },
                "last_builds": {
                    "dynamic": False,
                    "type": "nested",
                    "properties": {
                        "app_id": {
                            "type": "string"
                        },
                        "build_version": {
                            "type": "integer"
                        },
                        "build_version_date": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        }
                    }
                },
                "last_submission_for_user": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "app_id": {
                            "type": "string"
                        },
                        "build_id": {
                            "type": "string"
                        },
                        "build_version": {
                            "type": "integer"
                        },
                        "commcare_version": {
                            "type": "string"
                        },
                        "device_id": {
                            "type": "string"
                        },
                        "submission_date": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        }
                    }
                },
                "last_submissions": {
                    "dynamic": False,
                    "type": "nested",
                    "properties": {
                        "app_id": {
                            "type": "string"
                        },
                        "build_id": {
                            "type": "string"
                        },
                        "build_version": {
                            "type": "integer"
                        },
                        "commcare_version": {
                            "type": "string"
                        },
                        "device_id": {
                            "type": "string"
                        },
                        "submission_date": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        }
                    }
                },
                "last_sync_for_user": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "app_id": {
                            "type": "string"
                        },
                        "build_version": {
                            "type": "integer"
                        },
                        "sync_date": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        }
                    }
                },
                "last_syncs": {
                    "dynamic": False,
                    "type": "nested",
                    "properties": {
                        "app_id": {
                            "type": "string"
                        },
                        "build_version": {
                            "type": "integer"
                        },
                        "sync_date": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        }
                    }
                }
            }
        },
        "status": {
            "type": "string"
        },
        "user_data": {
            "enabled": False,
            "type": "object"
        },
        "user_data_es": {
            "dynamic": False,
            "type": "nested",
            "properties": {
                "key": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "value": {
                    "index": "analyzed",
                    "type": "string"
                }
            }
        },
        "user_location_id": {
            "index": "not_analyzed",
            "type": "string"
        },
        "username": {
            "analyzer": "standard",
            "fields": {
                "exact": {
                    "include_in_all": False,
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}
