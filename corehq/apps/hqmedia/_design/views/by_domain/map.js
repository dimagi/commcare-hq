function(doc){
    if(doc.doc_type === 'CommCareMultimedia' ||
        doc.doc_type === 'CommCareImage' ||
        doc.doc_type === 'CommCareAudio') {
        doc.owners.forEach(function (domain) {
            emit(domain, null);
        });
    }
}