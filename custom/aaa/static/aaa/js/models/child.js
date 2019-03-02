hqDefine("aaa/js/models/child", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData,
) {
    var childList = function (options, postData) {
        var self = {};
        self.id = options.id;
        self.name = ko.observable(options.name);
        self.age = ko.observable(options.age);
        self.gender = ko.observable(options.gender);
        self.lastImmunizationType = ko.observable(options.lastImmunizationType);
        self.lastImmunizationDate = ko.observable(options.lastImmunizationDate);

        self.name = ko.computed(function () {
            var url = initialPageData.reverse('unified_beneficiary_details');
            url = url.replace('details_type', 'child');
            url = url.replace('beneficiary_id', self.id);
            url = url + '?month=' + postData.selectedMonth() + '&year=' + postData.selectedYear();
            return '<a href="' + url + '">' + self.name() + '</a>';
        });

        self.age = ko.computed(function () {
            var age = parseInt(self.age());
            if (age < 12) {
                return age + " Mon"
            } else if (age === 12) {
                return "1 Yr"
            } else {
                return Math.floor(age / 12) + " Yr " + age % 12 + " Mon";
            }
        });

        self.lastImmunizationType = ko.computed(function () {
            return self.lastImmunizationType() === 1 ? 'Yes' : 'No';
        });

        return self;
    };

    var childListConfig = function () {
        var self = {};
        self.columns = [
            {data: 'name()', name: 'name', title: 'Name'},
            {data: 'age()', name: 'age', title: 'Age'},
            {data: 'gender()', name: 'gender', title: 'Gender'},
            {data: 'lastImmunizationType()', name: 'lastImmunizationType', title: 'Last Immunization Type'},
            {data: 'lastImmunizationDate()', name: 'lastImmunizationDate', title: 'Last Immunization Date'},
        ];
        return self;
    };


    var childModel = function(data) {
        var self = {};
        self.id = data.id;
        self.name = data.name;
        self.age = data.age;

        self.linkName = ko.computed(function () {
            return self.name + ' (' + self.age + ' Yrs)'
        });

        return self;
    };

    return {
        config: childListConfig,
        listView: childList,
        detailsView: '',
        childModel: childModel,
    }
});
