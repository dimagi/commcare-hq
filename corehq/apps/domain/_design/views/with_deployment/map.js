function (doc) {
    if (doc.doc_type == 'Domain' && doc.deployment.public) {
        emit([doc.deployment.date], null);
    }
}