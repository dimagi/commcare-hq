function (doc) {
    if (doc.doc_type === 'CommCareMultimedia' ||
        doc.doc_type === 'CommCareImage' ||
        doc.doc_type === 'CommCareAudio') {
        doc.tags.forEach(function (tag) {
            emit(tag, null);
        })
    }
}