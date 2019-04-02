/* global sinon, moment */

describe('Pregnant women models', function () {
    var pregnantWomenModels, reachUtils, clock, pageData;

    beforeEach(function () {
        pageData = hqImport('hqwebapp/js/initial_page_data');
        pregnantWomenModels = hqImport('aaa/js/models/pregnant_women');
        reachUtils = hqImport('aaa/js/utils/reach_utils');
        pageData.registerUrl('unified_beneficiary_details', 'unified_beneficiary_details/details_type/beneficiary_id/');
        var today = moment('2019-02-01').toDate();
        clock = sinon.useFakeTimers(today.getTime());
    });

    afterEach(function () {
        clock.restore();
    });

    describe('Pregnant women config model', function () {
        it('test model properties', function () {
            var configModel = pregnantWomenModels.config();
            var expectedColumns = [
                {data: 'name()', name: 'name', title: 'Name'},
                {data: 'age()', name: 'age', title: 'Age'},
                {data: 'pregMonth()', name: 'pregMonth', title: 'Preg. Month'},
                {data: 'highRiskPregnancy()', name: 'highRiskPregnancy', title: 'High Risk Pregnancy'},
                {data: 'noOfAncCheckUps()', name: 'noOfAncCheckUps', title: 'No. Of ANC Check-Ups'},
            ];
            assert.equal(expectedColumns.length, configModel.columns.length);
            _.each(expectedColumns, function (element, idx) {
                assert.equal(configModel.columns[idx].name, element.name);
                assert.equal(configModel.columns[idx].data, element.data);
                assert.equal(configModel.columns[idx].title, element.title);
            });
        });
    });

    describe('Pregnant women list view model', function () {
        it('test model properties', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var listView = pregnantWomenModels.listView(
                {
                    id: '1',
                    name: 'test Name',
                    age: 14,
                    pregMonth: 6,
                    highRiskPregnancy: 'yes',
                    noOfAncCheckUps: 5,
                },
                postData
            );
            assert.equal('1', listView.id);
            assert.equal('<a href="unified_beneficiary_details/pregnant_women/1/?month=3&year=2019">test Name</a>', listView.name());
            assert.equal(14, listView.age());
            assert.equal(6, listView.pregMonth());
            assert.equal('Yes', listView.highRiskPregnancy());
            assert.equal(5, listView.noOfAncCheckUps());
        });
    });

    describe('Pregnant women details view model', function () {
        it('test model properties', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var detailsView = pregnantWomenModels.detailsView(postData);
            assert.isTrue(detailsView.hasOwnProperty('personDetails'));
            assert.isTrue(detailsView.personDetails.hasOwnProperty('person'));
            assert.isTrue(detailsView.personDetails.hasOwnProperty('husband'));
            assert.isTrue(detailsView.hasOwnProperty('childDetails'));
            assert.isTrue(detailsView.hasOwnProperty('pregnantDetails'));
            assert.isTrue(detailsView.hasOwnProperty('sections'));

        });

        it('test sections', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var detailsView = pregnantWomenModels.detailsView(postData);
            assert.equal(11, detailsView.sections.length);
            var expectedSections = [
                'person_details',
                'children_list',
                'pregnancy_details',
                'pregnancy_risk',
                'antenatal_care_details',
                'consumables_disbursed',
                'immunization_counseling_details',
                'abortion_details',
                'maternal_death_details',
                'delivery_details',
                'postnatal_care_details',
            ];
            _.each(expectedSections, function (element, idx) {
                assert.equal(element, detailsView.sections[idx]);
            });
        });
    });

    describe('Pregnant women model', function () {
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
            var pregnantModel = pregnantWomenModels.pregnantModel(initialData, postData);
            assert.isTrue(pregnantModel.hasOwnProperty('dateOfLmp'));
            assert.isTrue(pregnantModel.hasOwnProperty('weightOfPw'));
            assert.isTrue(pregnantModel.hasOwnProperty('dateOfRegistration'));
            assert.isTrue(pregnantModel.hasOwnProperty('edd'));
            assert.isTrue(pregnantModel.hasOwnProperty('add'));
            assert.isTrue(pregnantModel.hasOwnProperty('lmp'));
            assert.isTrue(pregnantModel.hasOwnProperty('bloodGroup'));
            assert.isTrue(pregnantModel.hasOwnProperty('riskPregnancy'));
            assert.isTrue(pregnantModel.hasOwnProperty('referralDate'));
            assert.isTrue(pregnantModel.hasOwnProperty('hrpSymptoms'));
            assert.isTrue(pregnantModel.hasOwnProperty('illnessHistory'));
            assert.isTrue(pregnantModel.hasOwnProperty('referredOutFacilityType'));
            assert.isTrue(pregnantModel.hasOwnProperty('pastIllnessDetails'));
            assert.isTrue(pregnantModel.hasOwnProperty('ifaTablets'));
            assert.isTrue(pregnantModel.hasOwnProperty('thrDisbursed'));
            assert.isTrue(pregnantModel.hasOwnProperty('ttDoseOne'));
            assert.isTrue(pregnantModel.hasOwnProperty('ttDoseTwo'));
            assert.isTrue(pregnantModel.hasOwnProperty('ttBooster'));
            assert.isTrue(pregnantModel.hasOwnProperty('birthPreparednessVisitsByAsha'));
            assert.isTrue(pregnantModel.hasOwnProperty('birthPreparednessVisitsByAww'));
            assert.isTrue(pregnantModel.hasOwnProperty('counsellingOnMaternal'));
            assert.isTrue(pregnantModel.hasOwnProperty('counsellingOnEbf'));
            assert.isTrue(pregnantModel.hasOwnProperty('abortionDate'));
            assert.isTrue(pregnantModel.hasOwnProperty('abortionType'));
            assert.isTrue(pregnantModel.hasOwnProperty('abortionDays'));
            assert.isTrue(pregnantModel.hasOwnProperty('maternalDeathOccurred'));
            assert.isTrue(pregnantModel.hasOwnProperty('maternalDeathPlace'));
            assert.isTrue(pregnantModel.hasOwnProperty('maternalDeathDate'));
            assert.isTrue(pregnantModel.hasOwnProperty('authoritiesInformed'));
            assert.isTrue(pregnantModel.hasOwnProperty('dod'));
            assert.isTrue(pregnantModel.hasOwnProperty('assistanceOfDelivery'));
            assert.isTrue(pregnantModel.hasOwnProperty('timeOfDelivery'));
            assert.isTrue(pregnantModel.hasOwnProperty('dateOfDischarge'));
            assert.isTrue(pregnantModel.hasOwnProperty('typeOfDelivery'));
            assert.isTrue(pregnantModel.hasOwnProperty('timeOfDischarge'));
            assert.isTrue(pregnantModel.hasOwnProperty('placeOfBirth'));
            assert.isTrue(pregnantModel.hasOwnProperty('deliveryComplications'));
            assert.isTrue(pregnantModel.hasOwnProperty('placeOfDelivery'));
            assert.isTrue(pregnantModel.hasOwnProperty('complicationDetails'));
            assert.isTrue(pregnantModel.hasOwnProperty('hospitalType'));
            assert.isTrue(pregnantModel.hasOwnProperty('pncVisits'));
            assert.isTrue(pregnantModel.hasOwnProperty('ancVisits'));
        });

        it('test twelveWeeksPregnancyRegistration less then 12', function () {
            var pregnantModel = pregnantWomenModels.pregnantModel({});
            pregnantModel.updateModel({
                add: '2019-03-01',
                lmp: '2019-02-01',
            });
            assert.equal('Yes', pregnantModel.twelveWeeksPregnancyRegistration());
        });

        it('test twelveWeeksPregnancyRegistration greater then 12', function () {
            var pregnantModel = pregnantWomenModels.pregnantModel({});
            pregnantModel.updateModel({
                add: '2020-03-01',
                lmp: '2019-02-01',
            });
            assert.equal('No', pregnantModel.twelveWeeksPregnancyRegistration());
        });

        it('test pregnancyStatus - PNC', function () {
            var pregnantModel = pregnantWomenModels.pregnantModel({});
            pregnantModel.updateModel({
                add: '2019-03-01',
                lmp: '2019-03-15',
                edd: '2019-03-28',
            });
            assert.equal(3, pregnantModel.pregnancyStatus());
        });

        it('test pregnancyStatus - Due for delivery', function () {
            var pregnantModel = pregnantWomenModels.pregnantModel({});
            pregnantModel.updateModel({
                add: '2018-08-01',
                lmp: '2019-02-15',
                edd: '2019-03-28',
            });
            assert.equal(2, pregnantModel.pregnancyStatus());
        });

        it('test pregnancyStatus - Pregnancy', function () {
            var pregnantModel = pregnantWomenModels.pregnantModel({});
            pregnantModel.updateModel({
                add: '2018-08-01',
                lmp: '2019-02-15',
                edd: '2019-06-28',
            });
            assert.equal(1, pregnantModel.pregnancyStatus());
        });
    });

});
