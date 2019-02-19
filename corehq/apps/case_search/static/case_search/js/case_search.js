hqDefine('case_search/js/case_search', [
    'jquery',
    'knockout',
    'hqwebapp/js/alert_user',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    alertUser,
    initialPageData
) {
    'use strict';
    var caseSearchModel = function (caseDataUrl) {
        var self = {};
        self.type = ko.observable();
        self.owner_id = ko.observable();
        self.customQueryAddition = ko.observable();
        self.includeClosed = ko.observable(false);
        self.results = ko.observableArray();
        self.count = ko.observable();
        self.took = ko.observable();
        self.query = ko.observable();
        self.case_data_url = caseDataUrl;
        self.xpath = ko.observable();
        self.parameters = ko.observableArray();

        self.addParameter = function () {
            self.parameters.push({
                key: "",
                value: "",
                clause: "must",
                fuzzy: false,
                regex: '',
            });
        };
        self.removeParameter = function () {
            self.parameters.remove(this);
        };

        self.submit = function () {
            self.results([]);
            self.count("-");
            self.took(null);
            self.query(null);
            $.post({
                url: window.location.href,
                data: {q: JSON.stringify({
                    type: self.type(),
                    owner_id: self.owner_id(),
                    parameters: self.parameters(),
                    customQueryAddition: self.customQueryAddition(),
                    includeClosed: self.includeClosed(),
                    xpath: self.xpath(),
                }
                )},
                success: function (data) {
                    self.results(data.values);
                    self.count(data.count);
                    self.took(data.took);
                    self.query(data.query);
                },
                error: function (response) {
                    alertUser.alert_user(response.responseJSON.message, 'danger');
                },
            });
        };

        return self;
    };

    $(function () {
        $("#case-search").koApplyBindings(caseSearchModel(initialPageData.reverse('case_data')));
    });
});
