"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');

describe('PrecisionVsAchievementsTableModel', function() {
    var viewModel, districts, cbos;

    var ALL_OPTION = {'id': '', 'text': 'All'};

    pageData.registerUrl('champ_pva_table', 'champ_pva_table');

    beforeEach(function() {
        districts = [
            ALL_OPTION,
            {id: 'district1', value: 'district1'},
            {id: 'district2', value: 'district2'},
        ];
        cbos = [
            ALL_OPTION,
            {id: 'cbo1', value: 'cbo1', parent_id: 'district1'},
            {id: 'cbo2', value: 'cbo2', parent_id: 'district1'},
            {id: 'cbo3', value: 'cbo3', parent_id: 'district2'},
            {id: 'cbo4', value: 'cbo4', parent_id: 'district2'},
        ];
        viewModel = hqImport("champ/js/knockout/prevision_vs_achievement_table").model();
        viewModel.districts = districts;
        viewModel.cbos = cbos;
        viewModel.availableDistricts(districts);
        viewModel.availableCbos(cbos);
    });

    it('test onSelectOption', function() {
        var event = {
            added: ALL_OPTION,
        };
        viewModel.filters.client_type(['fsw', 'msm']);
        viewModel.onSelectOption(event, 'client_type');
        assert.deepEqual([''], viewModel.filters.client_type());
    });

    it('test districtOnSelect only district selected', function() {
        var event = {
            added: {id: 'district1', value: 'district1'},
        };
        assert.equal(3, viewModel.availableDistricts().length);
        assert.equal(5, viewModel.availableCbos().length);
        viewModel.filters.district(['district1']);
        viewModel.districtOnSelect(event);
        assert.equal(3, viewModel.availableCbos().length);
    });

    it('test districtOnSelect all option', function() {
        var event = {
            added: ALL_OPTION,
        };
        assert.equal(3, viewModel.availableDistricts().length);
        assert.equal(5, viewModel.availableCbos().length);
        viewModel.filters.district(['']);
        viewModel.districtOnSelect(event);
        assert.equal(5, viewModel.availableCbos().length);
    });
});
