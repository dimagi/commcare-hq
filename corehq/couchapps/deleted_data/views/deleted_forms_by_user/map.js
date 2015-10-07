function(doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/dates.js

    function get_user_id(xform_doc) {
        var meta = xform_doc.form.meta;
        if (meta) {
            return meta.userID;
        } else {
            return null;
        }
    }

    if (doc.doc_type == "XFormInstance-Deleted" && get_user_id(doc) !== null) {
        var date = parse_date(doc.received_on);
        emit([get_user_id(doc), date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), doc.xmlns], 1);
    }
}
