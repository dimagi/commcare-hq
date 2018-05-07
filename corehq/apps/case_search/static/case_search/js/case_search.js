/* globals hqDefine, ko, $ */

hqDefine('case_search/js/case_search', function(){
    'use strict';
    var caseSearchModel = function(caseDataUrl){
        var self = {};
        self.type = ko.observable();
        self.owner_id = ko.observable();
        self.customQueryAddition = ko.observable();
        self.includeClosed = ko.observable(false);
        self.results = ko.observableArray();
        self.count = ko.observable();
        self.case_data_url = caseDataUrl;
        self.xpath = ko.observable();
        self.parameters = ko.observableArray();

        self.addParameter = function(){
            self.parameters.push({
                key: "",
                value: "",
                clause: "must",
                fuzzy: false,
                regex: '',
            });
        };
        self.removeParameter = function(){
            self.parameters.remove(this);
        };

        self.submit = function(){
            self.results([]);
            self.count("-");
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
                success: function(data){
                    self.results(data.values);
                    self.count(data.count);
                },
                error: function(response){
                    var alertUser = hqImport("hqwebapp/js/alert_user").alert_user;
                    alertUser(response.responseJSON.message, 'danger');
                },
            });
        };

        return self;
    };

    $(function() {
        $("#case-search").koApplyBindings(caseSearchModel(hqImport("hqwebapp/js/initial_page_data").reverse('case_data')));
    });
});
