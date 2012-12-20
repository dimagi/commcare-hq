function(doc) {
    // !code util/reports_forms.js

    if(doc.doc_type === "XFormInstance" && get_user_id(doc) != null) {
        // Note: if the user_id is null, that likely means doc is a device log, so not a form we care about here.

        var completion_time = doc.form.meta.timeEnd,
            start_time = doc.form.meta.timeStart,
            submission_time = doc.received_on,
            user_id = get_user_id(doc),
            xmlns = doc.xmlns,
            app_id = doc.app_id || {};

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
            app_id: doc.app_id || {},
            app_info: get_app_id(doc),
            user_id: user_id,
            username: get_username(doc),
        };

        var times = {
            completion: completion_time,
            submission: submission_time,
        };

        for (var status in times) {
            emit([status,                   doc.domain, times[status]], emit_entry);
            emit([status+" xmlns",          doc.domain, xmlns,      times[status]], emit_entry);
            emit([status+" app",            doc.domain, app_id,     times[status]], emit_entry);
            emit([status+" user",           doc.domain, user_id,    times[status]], emit_entry);
            emit([status+" xmlns app",      doc.domain, xmlns, app_id,  times[status]], emit_entry);
            emit([status+" xmlns user",     doc.domain, xmlns, user_id, times[status]], emit_entry);
            emit([status+" xmlns app user", doc.domain, xmlns, app_id, user_id, times[status]], emit_entry);
        }

    }
}
