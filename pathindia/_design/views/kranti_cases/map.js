function(doc) {
    // !code util/pathindia.js

    if (isWomanCaseType(doc)
        && !doc.closed ){
        if (doc.pregnancy_confirmation === 'yes')
            emit([doc.user_id, doc.modified_on], 1);
    }
}