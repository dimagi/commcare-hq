function (doc) {
    try {
        if (doc.doc_type == "RepeatRecord")
        {

            index("repeater_id", doc.repeater_id);
            index("repeater_type", doc.repeater_type);
            index("domain", doc.domain);
            index("last_checked", doc.last_checked);
            index("next_check", doc.next_check);
            index("succeeded", doc.succeeded);
            index("payload_id", doc.payload_id);
        }
    }
    catch (err) {
        // search may not be configured, do nothing
    }
}
