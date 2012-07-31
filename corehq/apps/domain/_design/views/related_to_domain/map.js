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

    if (doc.domain) {
        // "public" if it's one of the public doctypes and it's the current version
        var public = DOC_TYPES[doc.doc_type] &&
            !((doc.doc_type === 'Application' || doc.doc_type === 'RemoteApp') && doc.copy_of);
        emit([doc.domain, public], {doc_type: doc.doc_type, _id: doc._id});
    }
}