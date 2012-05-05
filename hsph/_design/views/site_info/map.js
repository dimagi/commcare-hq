function(doc) {
    // !code util/xforms.js
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        isDCOSiteLogReport(doc)){
        var entry = {};
        if (doc.form.facility_name) {
            entry.facilityName = doc.form.facility_name;
            entry.updateDate = doc.form.meta.timeEnd;
        }
        if (doc.form.region_id)
            emit([doc.form.region_id, doc.form.district_id, doc.form.site_number], entry);
    }
}