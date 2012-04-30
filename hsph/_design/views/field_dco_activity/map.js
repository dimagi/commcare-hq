function(doc) {
    // !code util/xforms.js
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        (isDCOFollowUpReport(doc) || isDCOSiteLogReport(doc) || isDCOBirthRegReport(doc)) ){
        var info = doc.form.meta,
            entry = {};

        if (isDCOBirthRegReport(doc)) {
            entry.birthReg = true;
            entry.numBirths = calcNumBirths(doc);
            entry.registrationLength = get_form_filled_duration(doc);
            entry.contactProvided = isContactProvided(doc);
        } else if (isDCOSiteLogReport(doc)) {
            entry.siteVisit = true;
            entry.siteId = formatDCOSiteID(doc);
            entry.visitDate = info.timeEnd;
        } else if (isDCOFollowUpReport(doc)) {
            entry.homeVisit = true;
            entry.completed = !!(doc.form.result_follow_up > 0);
            var dateAdmitted = (doc.form.date_admission) ? new Date(doc.form.date_admission) : new Date(info.timeEnd);
            var timeEnd = new Date(info.timeEnd);
            entry.openedAt21 = !!(dateAdmitted.getTime() - timeEnd.getTime() >= 21*24*60*60*1000);
        }
        emit([getDCO(doc), getDCTL(doc), info.timeEnd], entry);
    }
}