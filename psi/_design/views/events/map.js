function (doc) {
    //!code util/emit_array.js
    if (doc.doc_type === 'XFormInstance' && (doc.domain === 'psi' || doc.domain === 'psi-unicef')) {
        var form = doc.form;

        if (form["@name"] !== 'Plays and Events') {
            return;
        }

        var data = {
            males: form.number_of_males || 0,
            females: form.number_of_females || 0,
            attendees: form.number_of_attendees || 0,
            leaflets: form.number_of_leaflets || 0,
            gifts: form.number_of_gifts || 0
        };

        var opened_on = form.meta.timeEnd;

        emit_array([doc.domain, form.activity_state, form.activity_district], [opened_on], data);
    }
}
