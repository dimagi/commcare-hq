function(doc) {
    // !code util/pathindia.js

    if (doc.doc_type === 'XFormInstance'
        && doc.domain === 'pathindia'
        && (isVisitForm(doc) || isRegistrationForm(doc)) ){
        var info = doc.form.meta;
        var entry = new PathIndiaReport(doc);

        if (isVisitForm(doc)) {
            entry.getAntenatalData();
            entry.getIntranatalData();
            entry.getPostnatalData();
        }

        entry.data.eligible = 1;
        entry.data.pregnant_visit = (doc.form.still_pregnant === 'yes' || doc.form.pregnancy_confirmation === 'yes');


        emit([info.userID, info.timeEnd], entry.data);
    }
}