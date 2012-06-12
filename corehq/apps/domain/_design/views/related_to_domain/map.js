function(doc) {
    var DOC_TYPES = { // use this object to look up case types
        'ExceptionRecord': false,
        'MessageLog': false,
        'RegistrationRequest': false,
        'SMSLog': false,
        'XFormInstance': false,
        'CommCareUser': false,
        'CommCareCase': false,
        'UserRole': true,
        'Application': true,
        'RemoteApp': true
    };

    if (doc.domain && DOC_TYPES[doc.doc_type]) {
        if ((doc.doc_type === 'Application' || doc.doc_type === 'RemoteApp') && doc.copy_of)
            return;
        emit(doc.domain, {doc_type: doc.doc_type, _id: doc._id});
    }
}