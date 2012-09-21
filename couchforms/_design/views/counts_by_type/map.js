function(doc) { 
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/dates.js
    
    if (doc["doc_type"] == "XFormInstance") {
        date = get_date(doc);
        if (!date) {
            date = Date();
        }
        emit([doc.xmlns, date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()], 1);
    } 
}
