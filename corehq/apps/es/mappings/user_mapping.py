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
            "type": "text"
        },
        "__group_ids": {
            "type": "keyword"
        },
        "__group_names": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        "analytics_enabled": {
            "type": "boolean"
        },
        "assigned_location_ids": {
            "type": "keyword"
        },
        "base_doc": {
            "type": "text"
        },
        "base_username": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
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
                            "type": "keyword"
                        },
                        "build_id": {
                            "type": "keyword"
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
                    "type": "text"
                },
                "device_id": {
                    "type": "keyword"
                },
                "last_used": {
                    "format": DATE_FORMATS_STRING,
                    "type": "date"
                }
            }
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
        "domain_membership": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "assigned_location_ids": {
                    "type": "text"
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
                "is_admin": {
                    "type": "boolean"
                },
                "location_id": {
                    "type": "keyword"
                },
                "override_global_tz": {
                    "type": "boolean"
                },
                "role_id": {
                    "type": "keyword"
                },
                "timezone": {
                    "type": "text"
                }
            }
        },
        "domain_memberships": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "assigned_location_ids": {
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
                "is_admin": {
                    "type": "boolean"
                },
                "location_id": {
                    "type": "keyword"
                },
                "override_global_tz": {
                    "type": "boolean"
                },
                "role_id": {
                    "type": "keyword"
                },
                "timezone": {
                    "type": "text"
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
                    "type": "keyword"
                },
                "signed": {
                    "type": "boolean"
                },
                "type": {
                    "type": "text"
                },
                "user_id": {
                    "type": "keyword"
                },
                "user_ip": {
                    "type": "text"
                },
                "version": {
                    "type": "text"
                }
            }
        },
        "first_name": {
            "type": "text"
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
            "type": "text"
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
                            "type": "keyword"
                        },
                        "build_id": {
                            "type": "keyword"
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
                    "type": "text"
                },
                "device_id": {
                    "type": "keyword"
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
            "type": "text"
        },
        "location_id": {
            "type": "keyword"
        },
        "password": {
            "type": "text"
        },
        "phone_numbers": {
            "type": "text"
        },
        "registering_device_id": {
            "type": "keyword"
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
                            "type": "keyword"
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
                            "type": "keyword"
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
                            "type": "keyword"
                        },
                        "build_id": {
                            "type": "keyword"
                        },
                        "build_version": {
                            "type": "integer"
                        },
                        "commcare_version": {
                            "type": "text"
                        },
                        "device_id": {
                            "type": "keyword"
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
                            "type": "keyword"
                        },
                        "build_id": {
                            "type": "keyword"
                        },
                        "build_version": {
                            "type": "integer"
                        },
                        "commcare_version": {
                            "type": "text"
                        },
                        "device_id": {
                            "type": "keyword"
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
                            "type": "keyword"
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
                            "type": "keyword"
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
            "type": "text"
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
                    "type": "keyword"
                },
                "value": {
                    "type": "text"
                }
            }
        },
        "user_location_id": {
            "type": "keyword"
        },
        "username": {
            "analyzer": "standard",
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}
