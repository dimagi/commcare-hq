function(doc) {
    // !code util/xforms.js
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        isDCOSiteLogReport(doc)){
        var info = (doc.form) ? doc.form : doc;
        emit([info.region_id, info.district_id, info.site_number], null);
    }
}