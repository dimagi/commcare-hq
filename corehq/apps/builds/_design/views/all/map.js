function (doc) {
    if (doc.doc_type === "CommCareBuild") {
        emit([doc.version, doc.build_number, doc.time], null);
    }
}