function (doc) {
    if (doc.doc_type === "SurveyKeyword") {
        emit([doc.domain, doc.keyword.toUpperCase()], null);
    }
}
