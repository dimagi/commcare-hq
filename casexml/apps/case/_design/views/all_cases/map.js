function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.user_id) {
        var owner_id = doc.owner_id || doc.user_id;
        var sort_by = doc.type + doc.name;

        if (sort_by && typeof(sort_by) === "string") {
            sort_by = sort_by.toLowerCase();

            emit(["all", doc.domain, sort_by], 1);
            emit(["all owner", doc.domain, owner_id, sort_by], 1);
            emit(["all type", doc.domain, doc.type, sort_by], 1);
            emit(["all type owner", doc.domain, doc.type, owner_id, sort_by], 1);

            var status = (doc.closed) ? "closed" : "open";
            emit([status, doc.domain, owner_id, sort_by], 1);
            emit([status+" owner", doc.domain, owner_id, sort_by], 1);
            emit([status+" type", doc.domain, doc.type, sort_by], 1);
            emit([status+" type owner", doc.domain, doc.type, owner_id, sort_by], 1);
        }
    }
}