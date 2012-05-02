function(doc) {
    // !code util/xforms.js
    // !code util/hsph.js

    if (isHSPHBirthCase(doc)
        && !doc.closed
        && doc.date_delivery){
        var entry = {
            region: doc.region_id,
            district: doc.district_id,
            siteNum: doc.site_number,
            patientId: doc.patient_id,
            hasContact: isContactProvided(doc),
            visitedDate: doc.closed_on,
            followupFormId: doc.xform_ids[Math.max(0, doc.xform_ids.length-1)],
            numBirths: calcNumBirths(doc),
            dateBirth: doc.date_delivery
        };
        var responseDatespan = calcHSPHBirthDatespan(doc);
        entry.startDate = (responseDatespan) ? responseDatespan.start : doc.opened_on;
        entry.endDate = (responseDatespan) ? responseDatespan.end : doc.opened_on;

        emit([doc.user_id, entry.region, entry.district, entry.siteNum, entry.dateBirth], entry);
    }
}