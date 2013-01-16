function (doc) {
    //!code util/emit_array.js
    //!code util/repeats.js

    if (doc.doc_type === 'XFormInstance' && (doc.domain === 'psi' || doc.domain === 'psi-unicef')) {
        var form = doc.form;

        if (form["@name"] !== 'Household Demonstration') {
            return;
        }

        var data = {
            demonstrations: count_in_repeats(form.visits, "hh_covered"),
            children: count_in_repeats(form.visits, "number_young_children_covered"),
            leaflets: count_in_repeats(form.visits, "leaflets_distributed"),
            kits: count_in_repeats(form.visits, "kits_sold")
        };

        var opened_on = form.meta.timeEnd;

        emit_array([form.activity_state, form.activity_district, form.activity_block, form.activity_village],
            [opened_on], data);
    }
}
