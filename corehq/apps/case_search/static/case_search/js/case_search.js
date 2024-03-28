hqDefine('case_search/js/case_search', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/bootstrap3/alert_user',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    _,
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
        self.results = ko.observableArray();
        self.count = ko.observable();
        self.took = ko.observable();
        self.query = ko.observable();
        self.profile = ko.observable();
        self.case_data_url = caseDataUrl;
        self.parameters = ko.observableArray();
        self.xpath_expressions = ko.observableArray();

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

        self.addXPath = function () {
            self.xpath_expressions.push({xpath: ""});
        };
        self.removeXPath = function () {
            self.xpath_expressions.remove(this);
        };

        self.showResults = ko.computed(function () {
            return !_.isUndefined(self.count()) && !_.isNaN(parseInt(self.count()));
        });

        self.searchButtonIcon = ko.observable("fa fa-search");
        self.profileButtonIcon = ko.observable("fa-regular fa-clock");

        self._submit = function (postData) {
            postData = postData || {};
            self.results([]);
            self.count("-");
            self.took(null);
            self.query(null);
            self.profile(null);
            self.searchButtonIcon("fa fa-spin fa-refresh");
            self.profileButtonIcon("fa fa-spin fa-refresh");
            $.post({
                url: window.location.href,
                data: _.extend(postData, {q: JSON.stringify({
                    type: self.type(),
                    owner_id: self.owner_id(),
                    parameters: self.parameters(),
                    customQueryAddition: self.customQueryAddition(),
                    xpath_expressions: _.pluck(self.xpath_expressions(), 'xpath'),
                }
                )}),
                success: function (data) {
                    self.results(data.values);
                    self.count(data.count);
                    self.took(data.took);
                    self.query(data.query);
                    if (postData.include_profile) {
                        self.profile(data.profile);
                    }
                    self.searchButtonIcon("fa fa-search");
                    self.profileButtonIcon("fa-regular fa-clock");
                },
                error: function (response) {
                    alertUser.alert_user(response.responseJSON.message, 'danger');
                },
            });
        };

        self.search = function () {
            self._submit();
        };

        self.searchWithProfile = function () {
            self._submit({
                include_profile: true,
            });
        };

        return self;
    };

    $(function () {
        $("#case-search").koApplyBindings(caseSearchModel(initialPageData.reverse('case_data')));
    });
});
