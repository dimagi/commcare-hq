function (doc) {
    if(doc.doc_type === "XFormInstance" && doc.form.meta) {
        var username = doc.form.meta.username;
        if (username !== "demo_user" && username !== "admin" && username !== "system") {
            emit([
                doc.domain,
                doc.form.meta.userID,
                username,
                doc.form.meta.deviceID
            ], {"start": doc.received_on, "end": doc.received_on, "count": 1});
        }
    }
}