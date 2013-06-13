function(doc) {
    // !code util/hsph.js
    // !code util/hsph_field_management.js
    
    if (!(
        isHSPHBirthRegForm(doc) ||
        isFIDALogSiteForm(doc)
    )) {
        return;
    }

    var form = doc.form;
        data = {};

    if (isHSPHBirthRegForm(doc)) {
        data = getContactData(form); 
        data.birthRegistrations = 1;
    } else if (isFIDALogSiteForm(doc)) {
        data.facilityVisits = 1;
    }

    emit([doc.domain, form.meta.userID, form.site_id, form.meta.timeEnd], data);
}
