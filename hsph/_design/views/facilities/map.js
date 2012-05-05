function(doc) {
    // !code util/xforms.js
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        isDCOSiteLogReport(doc)){
        var entry = new HSPHEntry(doc);
        entry.getSiteInfo();
        emit(entry.data.siteId, null);
    }
}