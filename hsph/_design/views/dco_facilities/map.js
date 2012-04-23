function(doc) {
    // !code util/xforms.js

    var birth_reg = "http://openrosa.org/formdesigner/FE77C4BD-38EE-499B-AC5E-D7279C83BDB5",
        site_visit = "http://openrosa.org/formdesigner/8412C3D0-F06C-49BF-9067-ED62E991F315";

    if (doc.doc_type === 'XFormInstance'
        && doc.domain === 'hsph'
        && (doc.xmlns === birth_reg || doc.xmlns == site_visit)
        && (doc.form.site_id || (doc.form.region_id && doc.form.district_id && doc.form.site_number))){
        var info = doc.form.meta;
        var entry = {
            siteId: (doc.form.site_id) ? doc.form.site_id : doc.form.region_id+doc.form.district_id+doc.form.site_number
        };
        entry.siteId = entry.siteId.replace(/ /g,'').toLowerCase();
        emit([entry.siteId], entry);
    }
}