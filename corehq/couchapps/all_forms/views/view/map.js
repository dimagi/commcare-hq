function(doc) {

    function get_user_id(xform_doc) {
        return (xform_doc.form.meta ? xform_doc.form.meta.userID : null);
    }

    function get_username(xform_doc) {
        return (xform_doc.form.meta ? xform_doc.form.meta.username : null);
    }

    var MISSING_APP_ID = "_MISSING_APP_ID";

    function get_app_id(xform_doc) {
        return xform_doc.app_id || MISSING_APP_ID;
    }

    if(doc.doc_type === "XFormInstance" && get_user_id(doc) != null) {
        // Note: if the user_id is null, that likely means doc is a device log, so not a form we care about here.

        var completion_time = doc.form.meta.timeEnd,
            start_time = doc.form.meta.timeStart,
            submission_time = doc.received_on,
            user_id = get_user_id(doc),
            xmlns = doc.xmlns,
            app_id = get_app_id(doc);

        var start_date = new Date(start_time),
            end_date = new Date(completion_time);
        var difference = end_date.getTime() - start_date.getTime();

        var emit_entry = {
            time: submission_time, // move to submission_time
            completion_time: completion_time,
            start_time: start_time,
            duration: difference,
            submission_time: submission_time,
            xmlns: xmlns,
            app_id: get_app_id(doc),
            user_id: user_id,
            username: get_username(doc)
        };

        if (xmlns) {
            emit(['submission', doc.domain, submission_time], emit_entry);
            emit(['submission xmlns', doc.domain, xmlns, submission_time], emit_entry);
            emit(['submission app', doc.domain, app_id, submission_time], emit_entry);
            emit(['submission user', doc.domain, user_id, submission_time], emit_entry);
            emit(['submission xmlns app', doc.domain, xmlns, app_id, submission_time], emit_entry);
            emit(['submission xmlns user', doc.domain, xmlns, user_id, submission_time], emit_entry);
        }
    }
}
