function(doc){
    if(doc.doc_type === 'CommCareMultimedia' ||
        doc.doc_type === 'CommCareImage' ||
        doc.doc_type === 'CommCareAudio' ||
        doc.doc_type === 'CommCareVideo') {
        doc.valid_domains.forEach(function (domain) {
            emit(domain, null);
        });
    }
}
