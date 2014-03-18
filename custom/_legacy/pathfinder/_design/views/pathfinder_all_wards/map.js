function (doc) {
    if (doc.doc_type == 'CommCareUser'
        && doc.domain == 'pathfinder'
        && doc.user_data)
    {
        var u = doc.user_data;
        emit([doc.domain, u.district, u.ward], null);
    }
}
