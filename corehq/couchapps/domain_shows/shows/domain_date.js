function (doc, req) {
    function get_date(doc){
        switch (doc.doc_type){
            case "CommCareCase":
            case "CommCareCase-Deleted":
                return doc.opened_on;
            case "XFormInstance":
            case "XFormInstance-Deleted":
            case "XFormError":
            case "XFormDuplicate":
            case "XFormDeprecated":
            case "XFormArchived":
            case "SubmissionErrorLog":
                return doc.received_on;
            case "CommCareUser":
            case "WebUser":
                return doc.created_on;
            case "Application":
            case "Application-Deleted":
            case "RemoteApp":
            case "RemoteApp-Deleted":
                return doc.copy_of ? doc.built_on : null;
            default:
                return null;
        }
    }

    function get_domains(doc) {
        var domains = [];
        if (doc.domain) {
            domains.push(doc.domain)
        }
        if (doc.domains && doc.domains.length) {
            for (i = 0; i < doc.domains.length; i += 1) {
                domains.push(doc.domains[i]);
            }
        }
        return domains;
    }

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
