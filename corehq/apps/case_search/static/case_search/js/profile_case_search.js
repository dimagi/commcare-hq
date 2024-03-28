'use strict';

hqDefine('case_search/js/profile_case_search', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/bootstrap3/alert_user',
], function (
    $,
    _,
    ko,
    alertUser
) {
    var caseSearchModel = function () {
        var self = {};
        self.appId = ko.observable();
        self.requestDict = ko.observable();
        self.results = ko.observable();
        self.browserTime = ko.observable();
        self.searchButtonIcon = ko.observable("fa fa-search");
        self.exampleRequestDict = JSON.stringify({
            "request_dict": {
                "_xpath_query": ["name: 'Ethan'", "subcase-exists(parent, name='Matilda')"],
                "case_type": ["patient"],
            },
        });

        self.search = function () {
            self.searchButtonIcon("fa fa-spin fa-refresh");
            let start = Date.now();
            $.post({
                url: window.location.href,
                data: {q: self.requestDict(), app_id: self.appId()},
                success: function (data) {
                    self.results(data);
                    self.searchButtonIcon("fa fa-search");
                    self.browserTime((Date.now() - start) / 1000);
                },
                error: function (response) {
                    alertUser.alert_user(response.responseJSON.message, 'danger');
                },
            });
        };

        return self;
    };

    $(function () {
        $("#profile-case-search").koApplyBindings(caseSearchModel());
    });
});
