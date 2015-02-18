function(doc) {
    if (doc._conflicts) {
        var domain = doc.domain ? doc.domain : null;
        if (!domain && doc.domains && doc.domains.length) {
            domain = doc.domains[0];
        }
        emit([domain, doc.doc_type], doc._conflicts.length);
    }
  }