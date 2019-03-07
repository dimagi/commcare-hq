hqDefine("aaa/js/models/child", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'aaa/js/models/person',
    'aaa/js/models/model_utils',
    'aaa/js/utils/chart_const',
], function (
    $,
    ko,
    _,
    initialPageData,
    personUtils,
    modelUtils,
    chartConst
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


    var childModel = function (data, postData) {
        var self = {};
        self.id = data.id || null;
        self.name = data.name || null;
        self.age = data.age || null;

        self.pregnancyLength = ko.observable();
        self.breastfeedingInitiated = ko.observable();
        self.babyCried = ko.observable();
        self.dietDiversity = ko.observable();
        self.birthWeight = ko.observable();
        self.dietQuantity = ko.observable();
        self.breastFeeding = ko.observable();
        self.handwash = ko.observable();
        self.exclusivelyBreastfed = ko.observable();

        self.pncVisits = ko.observableArray();

        self.vaccinationDetails = {
            atBirth: ko.observableArray(),
            sixWeek: ko.observableArray(),
            tenWeek: ko.observableArray(),
            fourteenWeek: ko.observableArray(),
            nineTwelveMonths: ko.observableArray(),
            sixTeenTwentyFourMonth: ko.observableArray(),
            twentyTwoSeventyTwoMonth: ko.observableArray(),
        };

        self.currentWeight = ko.observable();
        self.nrcReferred = ko.observable();
        self.referralDate = ko.observable();
        self.growthMonitoringStatus = ko.observable();
        self.previousGrowthMonitoringStatus = ko.observable();

        self.underweight = ko.observable();
        self.underweightStatus = ko.observable();
        self.stunted = ko.observable();
        self.stuntedStatus = ko.observable();
        self.wasting = ko.observable();
        self.wastingStatus = ko.observable();

        self.linkName = ko.computed(function () {
            var url = initialPageData.reverse('unified_beneficiary_details');
            url = url.replace('details_type', 'child');
            url = url.replace('beneficiary_id', 1);
            url = url + '?month=' + postData.selectedMonth() + '&year=' + postData.selectedYear();
            return '<a href="' + url + '">' + self.name + ' (' + self.age + ' Yrs)' + '</a>';
        });
        
        self.updateModel = function (data) {
            _.each(data, function (value, key) {
                self[key](value);
            });
        };

        self.updatePncVisits = function (data) {
            _.each(data, function (visit) {
                self.pncVisits.push(modelUtils.pncModel(visit));
            });
            while (self.pncVisits().length < 4) {
                self.pncVisits.push(modelUtils.pncModel({}));
            }
        };

        self.updateVaccinationDetails = function (data, period) {
            _.each(data, function (vitamin) {
                self.vaccinationDetails[period].push(modelUtils.vaccinationModel(vitamin));
            });
            while (self.vaccinationDetails[period]().length % 5 > 0) {
                self.vaccinationDetails[period].push(modelUtils.vaccinationModel({}));
            }
        };

        return self;
    };


    var childDetailsView = function (postData) {
        var self = {};
        self.personDetails = {
            person: ko.observable(personUtils.personModel),
            mother: ko.observable(personUtils.personModel),
            other: ko.observable(personUtils.personOtherInfoModel),
        };

        self.infantDetails = ko.observable(childModel({}, postData));

        self.postData = postData;

        self.sections = [
            'person_details',
            'infant_details',
            'child_postnatal_care_details',
            'vaccination_details',
            'growth_monitoring_details',
        ];

        self.weightForAgeChart = function (data) {
            var chart = nv.models.lineChart();
            chart.height(450);
            chart.margin({
                top: 20,
                right: 20,
                bottom: 50,
                left: 80,
            });
            chart.showLegend(false);
            chart.transitionDuration(350);
            chart.xAxis.axisLabel('Age (Months)');
            chart.xAxis.showMaxMin(true);
            chart.xAxis.tickValues([0, 12, 24, 36, 48, 60]);
            chart.yAxis.axisLabel('Weight (Kg)');
            chart.yAxis.tickFormat(d3.format(".1f"));
            chart.yAxis.rotateLabels(-90);
            chart.useInteractiveGuideline(true);
            d3.select('#weight_for_age_chart svg').datum([
                {
                    key: 'green',
                    type: 'area',
                    values: chartConst.weightForAge['M']['green'],
                    color: 'green',
                    area: true,
                },
                {
                    key: 'orange',
                    type: 'area',
                    values: chartConst.weightForAge['M']['orange'],
                    color: 'orange',
                    area: true,
                },
                {
                    key: 'red',
                    type: 'area',
                    values: chartConst.weightForAge['M']['red'],
                    color: 'red',
                    area: true,
                },
                {
                    key: 'line',
                    type: 'line',
                    values: data.points,
                    color: 'black',
                    strokeWidth: 2,
                    yAxis: 1,
                }
            ]).call(chart);
            nv.utils.windowResize(chart.update);
            return chart;
        };

        self.heightForAgeChart = function (data) {
            var chart = nv.models.lineChart();
            chart.height(450);
            chart.margin({
                top: 20,
                right: 20,
                bottom: 50,
                left: 80,
            });
            chart.showLegend(false);
            chart.transitionDuration(350);
            chart.xAxis.axisLabel('Age (Months)');
            chart.xAxis.showMaxMin(true);
            chart.xAxis.tickValues([0, 12, 24, 36, 48, 60]);
            chart.yAxis.axisLabel('Height (cm)');
            chart.yAxis.tickFormat(d3.format(".1f"));
            chart.yAxis.rotateLabels(-90);
            chart.useInteractiveGuideline(true);
            d3.select('#height_for_age_chart svg').datum([
                {
                    key: 'green',
                    type: 'area',
                    values: chartConst.heightForAge['M']['green'],
                    color: 'green',
                    area: true,
                },
                {
                    key: 'orange',
                    type: 'area',
                    values: chartConst.heightForAge['M']['orange'],
                    color: 'orange',
                    area: true,
                },
                {
                    key: 'red',
                    type: 'area',
                    values: chartConst.heightForAge['M']['red'],
                    color: 'red',
                    area: true,
                },
                {
                    key: 'line',
                    type: 'line',
                    values: data.points,
                    color: 'black',
                    strokeWidth: 2,
                    yAxis: 1,
                }
            ]).call(chart);
            nv.utils.windowResize(function() { chart.update() });
            return chart;
        };

        self.weightForHeightChart = function (data) {
            var chart = nv.models.lineChart();
            chart.height(450);
            chart.margin({
                top: 20,
                right: 20,
                bottom: 50,
                left: 80,
            });
            chart.showLegend(false);
            chart.transitionDuration(350);
            chart.xAxis.axisLabel('Height (Cm)');
            chart.xAxis.showMaxMin(true);
            chart.yAxis.axisLabel('Weight (Kg)');
            chart.yAxis.tickFormat(d3.format(".1f"));
            chart.yAxis.rotateLabels(-90);
            chart.useInteractiveGuideline(true);
            d3.select('#weight_for_height_chart svg').datum([
                {
                    key: 'green',
                    type: 'area',
                    values: chartConst.weightForHeight['M']['green'],
                    color: 'green',
                    area: true,
                },
                {
                    key: 'orange',
                    type: 'area',
                    values: chartConst.weightForHeight['M']['orange'],
                    color: 'orange',
                    area: true,
                },
                {
                    key: 'red',
                    type: 'area',
                    values: chartConst.weightForHeight['M']['red'],
                    color: 'red',
                    area: true,
                },
                {
                    key: 'line',
                    type: 'line',
                    values: data.points,
                    color: 'black',
                    strokeWidth: 2,
                    yAxis: 1,
                }
            ]).call(chart);
            nv.utils.windowResize(chart.update);
            return chart;
        };

        self.getPersonDetails = function () {
            var params = Object.assign({
                section: 'child',
                subsection: 'person_details',
                beneficiaryId: initialPageData.get('beneficiary_id'),
            }, self.postData);
            $.post(initialPageData.reverse('unified_beneficiary_details_api'), params, function (data) {
                self.personDetails.person(personUtils.personModel(data.person, self.postData));
                self.personDetails.mother(personUtils.personModel(data.mother, self.postData));
                self.personDetails.other(personUtils.personOtherInfoModel(data.other));
            });
        };

        self.getChildDetails = function (subsection) {
            var params = Object.assign({
                section: 'child',
                subsection: subsection,
                beneficiaryId: initialPageData.get('beneficiary_id'),
            }, self.postData);
            $.post(initialPageData.reverse('unified_beneficiary_details_api'), params, function (data) {
                if (subsection === 'child_postnatal_care_details') {
                    self.infantDetails().updatePncVisits(data.visits);
                } else {
                    self.infantDetails().updateModel(data);
                }
            });
        };

        self.getVaccinationDetails = function (period) {
            var params = Object.assign({
                section: 'child',
                subsection: 'vaccination_details',
                period: period,
                beneficiaryId: initialPageData.get('beneficiary_id'),
            }, self.postData);
            $.post(initialPageData.reverse('unified_beneficiary_details_api'), params, function (data) {
                self.infantDetails().updateVaccinationDetails(data.vitamins, period);
            });
        };

        self.getChartData = function (subsection) {
            var params = Object.assign({
                section: 'child',
                subsection: subsection,
                beneficiaryId: initialPageData.get('beneficiary_id'),
            }, self.postData);
            $.post(initialPageData.reverse('unified_beneficiary_details_api'), params, function (data) {
                var types = {
                    'weight_for_age_chart': self.weightForAgeChart,
                    'height_for_age_chart': self.heightForAgeChart,
                    'weight_for_height_chart': self.weightForHeightChart,
                };
                nv.addGraph(function () {
                    types[subsection](data);
                });
            });
        };

        self.callback = function () {
            self.getPersonDetails();
            self.getChildDetails('infant_details');
            self.getChildDetails('child_postnatal_care_details');
            self.getVaccinationDetails('atBirth');
            self.getVaccinationDetails('sixWeek');
            self.getVaccinationDetails('tenWeek');
            self.getVaccinationDetails('fourteenWeek');
            self.getVaccinationDetails('nineTwelveMonths');
            self.getVaccinationDetails('sixTeenTwentyFourMonth');
            self.getVaccinationDetails('twentyTwoSeventyTwoMonth');
            self.getChildDetails('growth_monitoring');
            self.getChartData('weight_for_age_chart');
            self.getChartData('height_for_age_chart');
            self.getChartData('weight_for_height_chart');
        };

        return self;
    };

    return {
        config: childListConfig,
        listView: childList,
        detailsView: childDetailsView,
        childModel: childModel,
    }
});
