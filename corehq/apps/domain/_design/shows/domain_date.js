function (doc, req) {
    // !code util/doc_utils.js

    if (doc !== null) {
        return {
            'json': {
                'domains': get_domains(doc),
                'date': get_date(doc),
                'doc_type': doc.doc_type
            }
        }
    }
}