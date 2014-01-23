function (doc) {
    if (doc.base_doc === "CouchUser") {
        var EULA_VERSION = "2.0"; // hardcoding this isn't the best idea but I can't think of a better way
        if (doc.hasOwnProperty("eulas")) {
            for (var i = 0; i < doc.eulas.length; i++) {
                var eula = doc.eulas[i];
                if (eula.version === EULA_VERSION && eula.signed === true) {
                    return;  // don't emit this user since the correct eula is signed
                }
            }
        }
        emit([doc.doc_type, doc.last_login], null);
    }
}
