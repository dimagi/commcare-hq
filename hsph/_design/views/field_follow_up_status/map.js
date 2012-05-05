function(doc) {
    // !code util/xforms.js
    // !code util/hsph.js

    if (isHSPHBirthCase(doc)){
        var entry = new HSPHEntry(doc);
        entry.getBirthStats();
        entry.getSiteInfo();
        entry.getCaseInfo();

        var status = (entry.data.isClosed) ? "closed" : "open";

        emit(["all", doc.user_id, getDCTL(doc), entry.data.startDate], entry.data);
        emit(["by_status", doc.user_id, getDCTL(doc), status, entry.data.startDate], entry.data);
        emit(["by_site", doc.user_id, getDCTL(doc), entry.data.region, entry.data.district, entry.data.siteNum, entry.data.startDate], entry.data);
        emit(["by_status_site", doc.user_id, getDCTL(doc), status, entry.data.region, entry.data.district, entry.data.siteNum, entry.data.startDate], entry.data);
    }
}