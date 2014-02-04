function (doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/dates.js

    function get_user_id(xform_doc) {
        var meta = xform_doc.form.meta;
        if (meta) return meta.userID;
    }

    function get_username(xform_doc) {
        var meta = xform_doc.form.meta;
        if (meta && meta.username) return meta.username;
        return null;
    }

    if (doc.doc_type == "XFormInstance" && get_user_id(doc) != null) {
        var date = parse_date(doc.received_on);
        var user_id = get_user_id(doc);
        var username = get_username(doc);
        var emitting_doc = {"domain": doc.domain, "user_id": user_id, "username": username};
        if (date) {
            emit([user_id, date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), doc.xmlns], emitting_doc);
        }
    }
}
