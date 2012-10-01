function (doc) {
    if (doc.base_doc === "ADMColumn"
        && (doc.is_default || doc.config_doc !== "ConfigurableADMColumn")) {
            var emit_entry = {
                name: doc.name,
                description: doc.description
            };
            if (doc.domain) {
                emit_entry['domain'] = doc.domain;
            }

            emit(["defaults all slug", doc.slug, doc._id], emit_entry);
            emit(["defaults all type", doc.doc_type, doc._id], emit_entry);

            if (doc.domain) {
                emit(["defaults domain slug", doc.domain, doc.slug, doc._id], emit_entry);
                emit(["defaults domain type ", doc.domain, doc.doc_type, doc._id], emit_entry);
            } else {
                emit(["defaults global slug", doc.slug, doc._id], emit_entry);
                emit(["defaults global type", doc.doc_type, doc._id], emit_entry);
            }

            if (doc.returns_numerical) {
                emit(["numerical slug", doc.slug, doc._id], emit_entry);
                emit(["numerical type", doc.doc_type, doc._id], emit_entry);
            }
    }
}
