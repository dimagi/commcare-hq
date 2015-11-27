function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.user_id && !doc.closed) {
        var owner_id = doc.owner_id || doc.user_id;
        var sort_by = doc.type + doc.name;

        if (sort_by && typeof(sort_by) === "string") {
            sort_by = sort_by.toLowerCase();

            emit(["open owner", doc.domain, owner_id, sort_by], 1);
            emit(["open type owner", doc.domain, doc.type, owner_id, sort_by], 1);
        }
    }
}
