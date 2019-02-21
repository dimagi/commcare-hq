hqDefine("aaa/js/reports/unified_beneficiary", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'aaa/js/utils/reach_utils',
], function (
    $,
    ko,
    _,
    initialPageData,
    reachUtils
) {
    var tableDom = '<i<t><"row"<"col-md-2"><"col-md-8 center"<"table_pagination"p>><"col-md-2"<"table_info"l>>>>';

    var childModel = function () {
        var childList = function (options) {
            var self = {};
            self.name = ko.observable(options.name);
            self.age = ko.observable(options.age);
            self.gender = ko.observable(options.gender);
            self.lastImmunizationType = ko.observable(options.lastImmunizationType);
            self.lastImmunizationDate = ko.observable(options.lastImmunizationDate);
            
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

        return {
            config: childListConfig,
            listView: childList
        }
    };

    var eligibleCoupleModel = function () {

        var eligibleCoupleList = function (options) {
            var self = {};
            self.name = ko.observable(options.name);
            self.age = ko.observable(options.age);
            self.currentFamilyPlanningMethod = ko.observable(options.currentFamilyPlanningMethod);
            self.adoptionDateOfFamilyPlaning = ko.observable(options.adoptionDateOfFamilyPlaning);

            self.currentFamilyPlanningMethod = ko.computed(function () {
                return self.currentFamilyPlanningMethod() === 1 ? 'Yes' : 'No';
            });

            return self;
        };

        var eligibleCoupleListConfig = function () {
            var self = {};
            self.columns = [
                {data: 'name()', name: 'name', title: 'Name'},
                {data: 'age()', name: 'age', title: 'Age'},
                {data: 'currentFamilyPlanningMethod()', name: 'currentFamilyPlanningMethod', title: 'Current Family Planning Method'},
                {data: 'adoptionDateOfFamilyPlaning()', name: 'adoptionDateOfFamilyPlaning', title: 'Adoption Date Of Family Planing'},
            ];
            return self;
        };

        return {
            config: eligibleCoupleListConfig,
            listView: eligibleCoupleList
        }
    };

    var pregnantWomenModel = function () {

        var pregnantWomenList = function (options) {
            var self = {};
            self.name = ko.observable(options.name);
            self.age = ko.observable(options.age);
            self.pregMonth = ko.observable(options.pregMonth);
            self.highRiskPregnancy = ko.observable(options.highRiskPregnancy);
            self.noOfAncCheckUps = ko.observable(options.noOfAncCheckUps);

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
    };

    var unifiedBeneficiary = function (options) {
        var self = {};
        self.sections = ko.observableArray();
        self.title = 'Unified Beneficiary';
        self.slug = 'unified_beneficiary';
        self.postData = reachUtils.postData({});
        self.localStorage = reachUtils.localStorage();
        self.localStorage.showModal(true);
        self.reachUtils = reachUtils.reachUtils();

        self.filters = {
            'month-year-filter': {},
            'location-filter': {},
            'beneficiary-type-filter': {},
        };

        self.dt = null;

        var views = {
            'eligible_couple': eligibleCoupleModel(),
            'pregnant_women': pregnantWomenModel(),
            'child': childModel(),
        };

        var selectedType = null;
        var reportListView = null;

        self.updateRows = function (rows) {
            var data = [];
            self.dt.clear();
            _.forEach(rows, function (row) {
                data.push(reportListView.listView(row))
            });
            return data;
        };

        self.updateTable = function () {
            if (selectedType !== null) {
                self.dt.clear().draw().destroy();
                $('#datatable').empty();
            }
            selectedType = self.postData.selectedBeneficiaryType();
            reportListView = views[selectedType];

            self.dt = $('#datatable').DataTable({
                dom: tableDom,
                columns: reportListView.config().columns,
                serverSide: true,
                ajax: function (data, callback, settings) {
                    /* TODO: check why the ajax function is calling when the table is removed.

                       For now, we compare selected BeneficiaryType with this in
                       ajax function context because without this we get the js error
                       that the 'datatables' can't fill the old table.

                       This is called for old table even when we run destroy() function which
                       should totally remove old definition
                    */
                    if (self.postData.selectedBeneficiaryType() === selectedType) {
                        var params = {
                            draw: data.draw,
                            length: data.length,
                            start: data.start,
                            sortColumn: data.columns[data.order[0].column].name,
                            sortColumnDir: data.order[0].dir,
                        };
                        $.post(initialPageData.reverse('unified_beneficiary_api'), Object.assign(params, self.postData), function (response) {
                            var rows = self.updateRows(response.rows);
                            callback({
                                draw: response.draw,
                                recordsTotal: response.recordsTotal,
                                recordsFiltered: response.recordsFiltered,
                                data: rows
                            })
                        });
                    }
                }
            });
        };

        self.callback = function () {
            self.updateTable();
        };

        self.isActive = function (slug) {
            return self.slug === slug;
        };

        return self;
    };

    $(function () {
        var model = unifiedBeneficiary();
        $('#aaa-dashboard').koApplyBindings(model);
    });

    return {
        unifiedBeneficiary: unifiedBeneficiary,
    };
});
