function(doc){
    if(doc.doc_type === 'CommCareMultimedia' ||
        doc.doc_type === 'CommCareImage' ||
        doc.doc_type === 'CommCareAudio') {
        emit(doc.file_hash, null);
    }
}