function (doc) {
    if ((doc.doc_type === "RemoteApp" || doc.doc_type === "RemoteApp-Deleted")
        && doc.copy_of === null) {
        var emit_entry = {
            app: {
                names: doc.name,
                id: doc._id,
                langs: doc.langs,
            },
            profile_url: doc.profile_url,
            is_deleted: doc.doc_type === "RemoteApp-Deleted",
        };
        var status = (emit_entry.is_deleted) ? "deleted" : "active";
        emit(["", doc.domain, doc._id], emit_entry);
        emit(["status", doc.domain, status, doc._id], emit_entry);
    }
}
