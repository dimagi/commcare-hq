hqDefine("aaa/js/models/pregnant_women", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    var pregnantWomenList = function (options, postData) {
        var self = {};
        self.id = options.id;
        self.name = ko.observable(options.name);
        self.age = ko.observable(options.age);
        self.pregMonth = ko.observable(options.pregMonth);
        self.highRiskPregnancy = ko.observable(options.highRiskPregnancy);
        self.noOfAncCheckUps = ko.observable(options.noOfAncCheckUps);


        self.name = ko.computed(function () {
            var url = initialPageData.reverse('unified_beneficiary_details');
            url = url.replace('details_type', 'pregnant_women');
            url = url.replace('beneficiary_id', self.id);
            url = url + '?month=' + postData.selectedMonth() + '&year=' + postData.selectedYear();
            return '<a href="' + url + '">' + self.name() + '</a>';
        });

        self.highRiskPregnancy = ko.computed(function () {
            return self.highRiskPregnancy === 1 ? 'Yes': 'No';
        });
        return self;
    };

    var pregnantWomenListConfig = function () {
        var self = {};
        self.columns = [
            {data: 'name()', name: 'name', title: 'Name'},
            {data: 'age()', name: 'age', title: 'Age'},
            {data: 'pregMonth()', name: 'pregMonth', title: 'Preg. Month'},
            {data: 'highRiskPregnancy()', name: 'highRiskPregnancy', title: 'High Risk Pregnancy'},
            {data: 'noOfAncCheckUps()', name: 'noOfAncCheckUps', title: 'No. Of ANC Check-Ups'},
        ];
        return self;
    };

    return {
        config: pregnantWomenListConfig,
        listView: pregnantWomenList
    }
});
