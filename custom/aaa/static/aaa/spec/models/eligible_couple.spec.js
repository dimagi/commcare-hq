/* global sinon, moment */


describe('Eligible Couple models', function () {
    var eligibleCoupleModels, reachUtils, clock, pageData;

    beforeEach(function () {
        pageData = hqImport('hqwebapp/js/initial_page_data');
        eligibleCoupleModels = hqImport('aaa/js/models/eligible_couple');
        reachUtils = hqImport('aaa/js/utils/reach_utils');
        pageData.registerUrl('unified_beneficiary_details', 'unified_beneficiary_details/details_type/beneficiary_id/');
        var today = moment('2020-01-01').toDate();
        clock = sinon.useFakeTimers(today.getTime());
    });

    afterEach(function () {
        clock.restore();
    });

    describe('eligible couple config model', function () {
        it('test model properties', function () {
            var config = eligibleCoupleModels.config();
            var expectedColumns = [
                {data: 'name()', name: 'name', title: 'Name'},
                {data: 'age()', name: 'dob', title: 'Age'},
                {data: 'currentFamilyPlanningMethod()', name: 'currentFamilyPlanningMethod', title: 'Current Family Planning Method'},
                {data: 'adoptionDateOfFamilyPlaning()', name: 'adoptionDateOfFamilyPlaning', title: 'Adoption Date Of Family Planing'},
            ];
            assert.equal(expectedColumns.length, config.columns.length);
            _.each(expectedColumns, function (element, idx) {
                assert.equal(config.columns[idx].name, element.name);
                assert.equal(config.columns[idx].data, element.data);
                assert.equal(config.columns[idx].title, element.title);
            });
        });
    });

    describe('eligible couple list view model', function () {
        it('test model properties', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var listView = eligibleCoupleModels.listView(
                {
                    id: '1',
                    name: 'test Name',
                    dob: '2017-04-11',
                    currentFamilyPlanningMethod: 'condom',
                    adoptionDateOfFamilyPlaning: '2019-03-01',
                },
                postData
            );
            assert.equal('1', listView.id);
            assert.equal('<a href="unified_beneficiary_details/eligible_couple/1/?month=3&year=2019">test Name</a>', listView.name());
            assert.equal('1 Yr 11 Mon', listView.age());
            assert.equal('condom', listView.currentFamilyPlanningMethod());
            assert.equal('2019-03-01', listView.adoptionDateOfFamilyPlaning());
        });
    });

    describe('eligible couple details view model', function () {
        it('test model properties', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var detailsModel = eligibleCoupleModels.detailsView(postData);
            assert.isTrue(detailsModel.hasOwnProperty('personDetails'));
            assert.isTrue(detailsModel.personDetails.hasOwnProperty('person'));
            assert.isTrue(detailsModel.personDetails.hasOwnProperty('husband'));
            assert.isTrue(detailsModel.hasOwnProperty('sections'));
            assert.isTrue(detailsModel.hasOwnProperty('childDetails'));
            assert.isTrue(detailsModel.hasOwnProperty('eligibleCoupleDetails'));
        });

        it('test sections', function () {
            var postData = reachUtils.postData({
                selectedMonth: 3,
                selectedYear: 2019,
            });
            var detailsModel = eligibleCoupleModels.detailsView(postData);
            assert.equal(3, detailsModel.sections.length);
            var expectedSections = [
                'person_details',
                'children_list',
                'eligible_couple_details',
            ];

            _.each(expectedSections, function (element, idx) {
                assert.equal(element, detailsModel.sections[idx]);
            });
        });
    });

    describe('eligible couple model', function () {
        it('test model properties', function () {
            var initialData = {
                maleChildrenBorn: 3,
                femaleChildrenBorn: 4,
                maleChildrenAlive: 2,
                femaleChildrenAlive: 4,
                familyPlaningMethod: 'test method',
                familyPlanningMethodDate: '2018-09-01',
                ashaVisit: 'home',
                previousFamilyPlanningMethod: 'previous method',
                preferredFamilyPlaningMethod: 'preferred method',
            };
            var detailsModel = eligibleCoupleModels.eligibleCoupleModel(initialData);
            assert.equal(3, detailsModel.maleChildrenBorn);
            assert.equal(4, detailsModel.femaleChildrenBorn);
            assert.equal(2, detailsModel.maleChildrenAlive);
            assert.equal(4, detailsModel.femaleChildrenAlive);
            assert.equal('test method', detailsModel.familyPlaningMethod);
            assert.equal('2018-09-01', detailsModel.familyPlanningMethodDate);
            assert.equal('home', detailsModel.ashaVisit);
            assert.equal('previous method', detailsModel.previousFamilyPlanningMethod);
            assert.equal('preferred method', detailsModel.preferredFamilyPlaningMethod);
            assert.equal('3 (Male), 4 (Female)', detailsModel.childrenBorn());
            assert.equal('2 (Male), 4 (Female)', detailsModel.childrenAlive());
        });
    });
});
