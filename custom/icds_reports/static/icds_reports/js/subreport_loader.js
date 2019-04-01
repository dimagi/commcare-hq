var subReportModal = hqImport("icds_reports/js/base").subReportModal;
var queryUrl = hqImport("hqwebapp/js/initial_page_data").get("query_url");
var dataProviders = hqImport("hqwebapp/js/initial_page_data").get("data_providers_json");
for (var i = 0; i < dataProviders.length; i++) {
    var provider = dataProviders[i];
    var modal = subReportModal({
            providerSlug: provider.provider_slug,
            queryUrl: queryUrl
        });
    ko.applyBindings(
        modal,
        document.getElementById(provider.provider_slug)
    );
    modal.init();
}
