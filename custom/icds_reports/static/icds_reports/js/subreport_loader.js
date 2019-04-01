hqDefine("icds_reports/js/subreport_loader", function() {
    var subReportModal = function(options){
        var self = {};

        self.providerSlug = options.providerSlug;
        self.loading = ko.observable(true);
        self.queryUrl = options.queryUrl;

        self.init = function(){
            setTimeout(function(){
                $("#"+self.providerSlug).html("<h1>Got it!"+self.providerSlug+"<h1>");
            }, 2000);
            self.loading(false);
        };
        return self;
    };

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
        modal.init()
    }
});
