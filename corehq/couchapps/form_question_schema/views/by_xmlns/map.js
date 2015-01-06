function (doc) {
    if (doc.doc_type === "FormQuestionSchema") {
        emit([doc.domain, doc.app_id, doc.xmlns], null);
    }
}
