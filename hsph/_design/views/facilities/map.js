function(doc) {
    // !code util/xforms.js
    // !code util/hsph.js

    if (isHSPHForm(doc) &&
        isDCOSiteLogReport(doc)){
        emit(formatDCOSiteID(doc), null);
    }
}