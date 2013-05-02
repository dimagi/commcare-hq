function (doc) {
    if (doc.doc_type === "Domain" && !doc.is_snapshot) {
        emit([doc.organization, doc.hr_name], null);
    }
}