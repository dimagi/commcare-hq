from corehq.util.couch import DocUpdate


def migrate_repeater(repeater_doc):
    if "use_basic_auth" in repeater_doc:
        use_basic_auth = repeater_doc['use_basic_auth'] == True
        del repeater_doc['use_basic_auth']
        if use_basic_auth:
            repeater_doc["auth_type"] = "basic"
        return DocUpdate(repeater_doc)
