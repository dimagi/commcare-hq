function (doc) {
    var media = 0, attachments = {}, value;

    if (doc.doc_type === "XFormInstance") {
        if (doc.xmlns) {
            for (var key in doc._attachments) {
                if (doc._attachments.hasOwnProperty(key) &&
                    doc._attachments[key].content_type !== "text/xml") {
                    media += 1;
                    attachments[key] = doc._attachments[key];
                }
            }
            if (media > 0) {
                value = {
                    xmlns: doc.xmlns,
                    attachments: attachments,
                    date: doc.received_on
                };
                emit([doc.domain, doc.app_id, doc.xmlns, doc.received_on], value);
            }
        }
    }
}
