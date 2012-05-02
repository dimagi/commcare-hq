function(doc) {
    // !code util/xforms.js
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        isDCOBirthRegReport(doc) &&
        doc.form.mother_delivered_or_referred === "delivered"){
        var info = doc.form.meta,
            entry = {};

        entry.numBirths = calcNumBirths(doc);
        entry.registrationLength = get_form_filled_duration(doc);
        entry.region = doc.form.region_id;
        entry.district = doc.form.district_id;
        entry.siteNum = doc.form.site_number;

        emit([entry.region, entry.district, entry.siteNum, info.timeEnd], entry);
    }
}