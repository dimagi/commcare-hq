function (doc) {
    var get_form_filled_duration = function (xform_doc) {
        // in milliseconds
        if (xform_doc.form.meta && xform_doc.form.meta.timeEnd && xform_doc.form.meta.timeStart) {
            return new Date(xform_doc.form.meta.timeEnd).getTime() -
                new Date(xform_doc.form.meta.timeStart).getTime();
        }
        return null;
    },
        duration, form_date, xmlns, userID, domain;

    // for now incude all non-device-reports in this report
    if (doc.doc_type === "XFormInstance" &&
            doc.xmlns !== "http://code.javarosa.org/devicereport") {
        if (duration) {
            domain = doc.domain;
            duration = get_form_filled_duration(doc);
            xmlns = doc.xmlns;
            userID = doc.form.meta.userID;
            form_date = doc.received_on;
            emit(["dx", domain, form_date, xmlns], duration);
            emit(["udx", domain, userID, form_date, xmlns], duration);
            emit(["xdu", domain, xmlns, form_date, userID], duration);
        }
    }
}