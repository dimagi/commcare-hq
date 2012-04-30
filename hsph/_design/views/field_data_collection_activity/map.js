function(doc) {
    // !code util/xforms.js
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        (isDCOSiteLogReport(doc) || isDCOBirthRegReport(doc))){
        var info = doc.form.meta,
            entry = {};
        entry.siteId = formatDCOSiteID(doc);

        if (isDCOSiteLogReport(doc)) {
            entry.siteVisit = true;
        } else if (isDCOBirthRegReport(doc)) {
            entry.birthReg = true;
            entry.numBirths = calcNumBirths(doc);
            log(entry.numBirths);
            entry.contactProvided = isContactProvided(doc);
        }

        emit([entry.siteId, getDCO(doc), getDCTL(doc), info.timeEnd], entry);
    }
}