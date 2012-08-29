function (doc) {
    if (doc.doc_type === 'CommCareMultimedia' ||
        doc.doc_type === 'CommCareImage' ||
        doc.doc_type === 'CommCareAudio') {
        doc.shared_by.forEach(function (domain) {
            if (doc.tags[domain] && doc.tags[domain].length > 0) {
                doc.tags[domain].forEach(function (tag) {
                    emit(tag, null);
                });
            }
        });
    }
}