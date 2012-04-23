function(doc) {
    // !code util/xforms.js

    var birth_reg = "http://openrosa.org/formdesigner/FE77C4BD-38EE-499B-AC5E-D7279C83BDB5",
        site_visit = "http://openrosa.org/formdesigner/8412C3D0-F06C-49BF-9067-ED62E991F315";

    if (doc.doc_type === 'XFormInstance'
        && doc.domain === 'hsph'
        && (doc.xmlns === birth_reg || doc.xmlns == site_visit)){
        var info = doc.form.meta,
            entry = {};

        if (doc.xmlns === birth_reg) {
            entry.birthReg = true;
            entry.numBirths = (doc.form.multiple_birth === 'yes') ? parseInt(doc.form.multiple_birth_number) : 1;
            entry.registrationLength = get_form_filled_duration(doc);
            entry.contactProvided = !!(doc.form.phone_mother === 'yes' ||
                    doc.form.phone_husband === 'yes' ||
                    doc.form.phone_house === 'yes' ||
                    doc.form.phone_asha === 'yes');
        }
        if (doc.xmlns === site_visit ||
            (doc.form.site_id || (doc.form.region_id && doc.form.district_id && doc.form.site_number)) ) {
            entry.siteVisit = true;
            entry.siteId = (doc.form.site_id) ? doc.form.site_id : doc.form.region_id+doc.form.district_id+doc.form.site_number;
            entry.visitDate = info.timeEnd;
        }
        emit([info.userID, info.timeEnd], entry);
    }
}