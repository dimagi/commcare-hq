function(doc) {
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        (isDCOSiteLogReport(doc) || isCITLReport(doc)) ){
        var info = doc.form.meta,
            entry = new HSPHEntry(doc);
        entry.getSiteInfo();
        entry.getCITLInfo();
        entry.data.updateDate = info.timeEnd;

        if (entry.data.region) {
            emit(["all", entry.data.region, entry.data.district, entry.data.siteNum, info.timeEnd], entry.data);
            emit(["status", entry.data.region, entry.data.district, entry.data.siteNum, entry.data.facilityStatus, info.timeEnd], entry.data);
            emit(["type", entry.data.region, entry.data.district, entry.data.siteNum, entry.data.IHFCHF, info.timeEnd], entry.data);
            emit(["status_type", entry.data.region, entry.data.district, entry.data.siteNum, entry.data.facilityStatus, entry.data.IHFCHF, info.timeEnd], entry.data);
        }
    }
}