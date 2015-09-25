function (doc) {
    if (doc.doc_type === 'CallCenterIndicatorConfig') {
        emit(doc.domain, null)
    }
}
