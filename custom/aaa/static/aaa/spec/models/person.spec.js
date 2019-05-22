/* global sinon, moment */

describe('Person models', function () {
    var personModels, reachUtils, clock, pageData;

    beforeEach(function () {
        pageData = hqImport('hqwebapp/js/initial_page_data');
        personModels = hqImport('aaa/js/models/person');
        reachUtils = hqImport('aaa/js/utils/reach_utils');
        pageData.registerUrl('unified_beneficiary_details', 'unified_beneficiary_details/details_type/beneficiary_id/');
        var today = moment('2020-01-01').toDate();
        clock = sinon.useFakeTimers(today.getTime());
    });

    afterEach(function () {
        clock.restore();
    });

    it('test model properties', function () {
        var postData = reachUtils.postData({
            selectedMonth: 3,
            selectedYear: 2019,
        });
        var personModel = personModels.personModel({}, postData);
        assert.isTrue(personModel.hasOwnProperty('id'));
        assert.isTrue(personModel.hasOwnProperty('name'));
        assert.isTrue(personModel.hasOwnProperty('gender'));
        assert.isTrue(personModel.hasOwnProperty('status'));
        assert.isTrue(personModel.hasOwnProperty('dob'));
        assert.isTrue(personModel.hasOwnProperty('marriedAt'));
        assert.isTrue(personModel.hasOwnProperty('aadhaarNo'));
        assert.isTrue(personModel.hasOwnProperty('address'));
        assert.isTrue(personModel.hasOwnProperty('subcentre'));
        assert.isTrue(personModel.hasOwnProperty('village'));
        assert.isTrue(personModel.hasOwnProperty('anganwadiCentre'));
        assert.isTrue(personModel.hasOwnProperty('phone'));
        assert.isTrue(personModel.hasOwnProperty('religion'));
        assert.isTrue(personModel.hasOwnProperty('caste'));
        assert.isTrue(personModel.hasOwnProperty('bplOrApl'));
    });

    it('test age', function () {
        var postData = reachUtils.postData({
            selectedMonth: 3,
            selectedYear: 2019,
        });
        var initialData = {
            dob: '2018-09-01',
        };
        var personModel = personModels.personModel(initialData, postData);
        assert.equal('7 Mon', personModel.age());
    });

    it('test gender', function () {
        var postData = reachUtils.postData({
            selectedMonth: 3,
            selectedYear: 2019,
        });
        var initialData = {
            sex: 'M',
        };
        var personModel = personModels.personModel(initialData, postData);
        assert.equal('Male', personModel.gender());
    });

    it('test aadhaarNo', function () {
        var postData = reachUtils.postData({
            selectedMonth: 3,
            selectedYear: 2019,
        });
        var initialData = {
            has_aadhar_number: 1,
        };
        var personModel = personModels.personModel(initialData, postData);
        assert.equal('Yes', personModel.aadhaarNo());
    });

    it('test nameLink', function () {
        var postData = reachUtils.postData({
            selectedMonth: 3,
            selectedYear: 2019,
        });
        var initialData = {
            id: 1,
            name: 'test Person',
        };
        var personModel = personModels.personModel(initialData, postData);
        assert.equal('<a href="unified_beneficiary_details/eligible_couple/1/?month=3&year=2019">test Person</a>', personModel.nameLink());
    });
});
