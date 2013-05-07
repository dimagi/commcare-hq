function(doc) {
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        (isDCOSiteLogReport(doc) || isCITLReport(doc) || isDCOBirthRegReport(doc) || isDCCFollowUpReport(doc) || isDCOFollowUpReport(doc) ) ){
        var info = doc.form.meta,
            entry = new HSPHEntry(doc);
        entry.getSiteInfo();
        entry.getBirthStats();
        entry.getCITLInfo();

        if (isDCOBirthRegReport(doc)  || isDCOFollowUpReport(doc)) {
            entry.data.outcomeDataType = true;
        } else if (isDCCFollowUpReport(doc)) {
            entry.data.processDataType = true;
        }

        entry.data.userId = info.userID;
        entry.data.DCTL = "FIX ME PLS";

        if (entry.data.region) {
            emit(["full", entry.data.siteId, entry.data.region, entry.data.district, entry.data.siteNum, info.timeEnd], entry.data);
            emit(["district", entry.data.siteId, entry.data.region, entry.data.district, info.timeEnd], entry.data);
            emit(["region", entry.data.siteId, entry.data.region, info.timeEnd], entry.data);
            emit(["all", entry.data.siteId, info.timeEnd], entry.data);
        }
    }
}