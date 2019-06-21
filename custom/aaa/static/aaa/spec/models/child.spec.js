/* global sinon, moment */

describe('Child models', function () {
    var childModels, reachUtils, clock, pageData;

    beforeEach(function () {
        pageData = hqImport('hqwebapp/js/initial_page_data');
        pageData.registerUrl('unified_beneficiary_details', 'unified_beneficiary_details/details_type/beneficiary_id/');
        childModels = hqImport('aaa/js/models/child');
        reachUtils = hqImport('aaa/js/utils/reach_utils');
        pageData.registerUrl('unified_beneficiary_details', 'unified_beneficiary_details/details_type/beneficiary_id/');
        var today = moment('2020-01-01').toDate();
        clock = sinon.useFakeTimers(today.getTime());
    });

    afterEach(function () {
        clock.restore();
    });

    describe('child config model', function () {
        it('test model properties', function () {
            var childListConfig = childModels.config();
            var expectedColumns = [
                {data: 'name()', name: 'name', title: 'Name'},
                {data: 'age()', name: 'dob', title: 'Age'},
                {data: 'gender()', name: 'gender', title: 'Gender'},
                {data: 'lastImmunizationType()', name: 'lastImmunizationType', title: 'Last Immunization Type'},
                {data: 'lastImmunizationDate()', name: 'lastImmunizationDate', title: 'Last Immunization Date'},
            ];
            assert.equal(expectedColumns.length, childListConfig.columns.length);
            _.each(expectedColumns, function (element, idx) {
                assert.equal(childListConfig.columns[idx].name, element.name);
                assert.equal(childListConfig.columns[idx].data, element.data);
                assert.equal(childListConfig.columns[idx].title, element.title);
            });
        });
    });

    describe('child list view model', function () {
        it('test model properties', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var childListModel = childModels.listView(
                {
                    id: '1',
                    name: 'test Name',
                    dob: '2017-04-11',
                    gender: 'Male',
                    lastImmunizationType: 1,
                    lastImmunizationDate: '2019-03-01',
                },
                postData
            );
            assert.equal('1', childListModel.id);
            assert.equal('<a href="unified_beneficiary_details/child/1/?month=3&year=2019">test Name</a>', childListModel.name());
            assert.equal('1 Yr 11 Mon', childListModel.age());
            assert.equal('Male', childListModel.gender());
            assert.equal('Yes', childListModel.lastImmunizationType());
            assert.equal('2019-03-01', childListModel.lastImmunizationDate());
        });

        it('test lastImmunizationDate should be N/A when lastImmunizationType is null', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var childListModel = childModels.listView(
                {
                    id: '1',
                    name: 'test Name',
                    dob: '2017-04-11',
                    gender: 'Male',
                    lastImmunizationType: null,
                    lastImmunizationDate: '',
                },
                postData
            );
            assert.equal('No', childListModel.lastImmunizationType());
            assert.equal('N/A', childListModel.lastImmunizationDate());
        });
    });

    describe('child details view model', function () {
        it('test model properties', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var childDetailsModel = childModels.detailsView(postData);
            assert.isTrue(childDetailsModel.hasOwnProperty('personDetails'));
            assert.isTrue(childDetailsModel.personDetails.hasOwnProperty('person'));
            assert.isTrue(childDetailsModel.personDetails.hasOwnProperty('mother'));
            assert.isTrue(childDetailsModel.hasOwnProperty('sections'));
        });

        it('test sections', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var childDetailsModel = childModels.detailsView(postData);
            assert.equal(5, childDetailsModel.sections.length);
            var expectedSections = [
                'person_details',
                'infant_details',
                'child_postnatal_care_details',
                'vaccination_details',
                'growth_monitoring_details',
            ];
            _.each(expectedSections, function (element, idx) {
                assert.equal(element, childDetailsModel.sections[idx]);
            });
        });
    });

    describe('child model', function () {
        it('test model properties', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var initialData = {
                id: 1,
                name: 'test Child',
                dob: '2017-01-01',
            };
            var childModel = childModels.childModel(initialData, postData);
            assert.isTrue(childModel.hasOwnProperty('id'));
            assert.isTrue(childModel.hasOwnProperty('name'));
            assert.isTrue(childModel.hasOwnProperty('dob'));
            assert.isTrue(childModel.hasOwnProperty('pregnancyLength'));
            assert.isTrue(childModel.hasOwnProperty('breastfeedingInitiated'));
            assert.isTrue(childModel.hasOwnProperty('babyCried'));
            assert.isTrue(childModel.hasOwnProperty('dietDiversity'));
            assert.isTrue(childModel.hasOwnProperty('birthWeight'));
            assert.isTrue(childModel.hasOwnProperty('dietQuantity'));
            assert.isTrue(childModel.hasOwnProperty('breastFeeding'));
            assert.isTrue(childModel.hasOwnProperty('handwash'));
            assert.isTrue(childModel.hasOwnProperty('exclusivelyBreastfed'));
            assert.isTrue(childModel.hasOwnProperty('pncVisits'));
            assert.isTrue(childModel.hasOwnProperty('vaccinationDetails'));
            assert.isTrue(childModel.hasOwnProperty('currentWeight'));
            assert.isTrue(childModel.hasOwnProperty('nrcReferred'));
            assert.isTrue(childModel.hasOwnProperty('referralDate'));
            assert.isTrue(childModel.hasOwnProperty('growthMonitoringStatus'));
            assert.isTrue(childModel.hasOwnProperty('previousGrowthMonitoringStatus'));
            assert.isTrue(childModel.hasOwnProperty('underweight'));
            assert.isTrue(childModel.hasOwnProperty('underweightStatus'));
            assert.isTrue(childModel.hasOwnProperty('stunted'));
            assert.isTrue(childModel.hasOwnProperty('stuntedStatus'));
            assert.isTrue(childModel.hasOwnProperty('wasting'));
            assert.isTrue(childModel.hasOwnProperty('wastingStatus'));
        });

        it('test age function in child model', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var initialData = {
                id: 1,
                name: 'test Child',
                dob: '2017-03-12',
            };
            var childModel = childModels.childModel(initialData, postData);
            assert.equal('2 Yr 9 Mon', childModel.age());
        });

        it('test linkName function in child model', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var initialData = {
                id: 1,
                name: 'test Child',
                dob: '2017-03-12',
            };
            var childModel = childModels.childModel(initialData, postData);
            assert.equal('<a href="unified_beneficiary_details/child/1/?month=3&year=2019">test Child (2 Yr 9 Mon)</a>', childModel.linkName());
        });

        it('test updateModel', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var initialData = {
                id: 1,
                name: 'test Child',
                dob: '2017-03-12',
            };
            var childModel = childModels.childModel(initialData, postData);
            assert.equal(void(0), childModel.pregnancyLength());
            childModel.updateModel({pregnancyLength: 12});
            assert.equal(12, childModel.pregnancyLength());
        });
    });

});
