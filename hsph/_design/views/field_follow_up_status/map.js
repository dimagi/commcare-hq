function(doc) {
    // !code util/xforms.js
    // !code util/hsph.js

    if (isHSPHBirthCase(doc)){
        var entry = {
                region: doc.region_id,
                district: doc.district_id,
                siteNum: doc.site_number,
                isClosed: doc.closed,
                patientId: doc.patient_id,
                hasContact: isContactProvided(doc),
                visitedDate: doc.closed_on,
                followupFormId: doc.xform_ids[Math.max(0, doc.xform_ids.length-1)],
                numBirths: calcNumBirths(doc),
                dateBirth: doc.date_delivery,
                nameMother: doc.name_mother,
                address: doc.house_address
            };
        var responseDatespan = calcHSPHBirthDatespan(doc);
        entry.startDate = (responseDatespan) ? responseDatespan.start : doc.opened_on;
        entry.endDate = (responseDatespan) ? responseDatespan.end : doc.opened_on;

        if (doc.follow_up_type === 'dcc')
            entry.dccFollowUp = true;
        else if (doc.follow_up_type === 'dco')
            entry.dcoFollowUp = true;

        var status = (entry.isClosed) ? "closed" : "open";

        emit(["all", doc.user_id, getDCTL(doc), entry.startDate], entry);
        emit(["by_status", doc.user_id, getDCTL(doc), status, entry.startDate], entry);
        emit(["by_site", doc.user_id, getDCTL(doc), entry.region, entry.district, entry.siteNum, entry.startDate], entry);
        emit(["by_status_site", doc.user_id, getDCTL(doc), status, entry.region, entry.district, entry.siteNum, entry.startDate], entry);
    }
}