function(doc) {
    // !code util/xforms.js
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        isDCOSiteLogReport(doc)){

        var info = doc.form.meta,
            entry = {
                region: doc.form.region_id,
                district: doc.form.district_id,
                siteId: formatDCOSiteID(doc)
            };

        emit([doc.id, "all", info.timeEnd], entry);

        emit([doc.id, "region", entry.region, info.timeEnd], entry);
        emit([doc.id, "district", entry.district, info.timeEnd], entry);
        emit([doc.id, "site", entry.siteId, info.timeEnd], entry);

        emit([doc.id, "region_district", entry.region, entry.district, info.timeEnd], entry);
        emit([doc.id, "region_site", entry.region, entry.siteId, info.timeEnd], entry);
        emit([doc.id, "district_site", entry.district, entry.siteId, info.timeEnd], entry);

        emit([doc.id, "region_district_site", entry.region, entry.district, entry.siteId, info.timeEnd], entry);
    }
}