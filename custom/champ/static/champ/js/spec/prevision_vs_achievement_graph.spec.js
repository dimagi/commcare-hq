"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');

describe('PrecisionVsAchievementsGraphModel', function() {
    var viewModel, districts, cbos, clienttypes, userpls;

    var ALL_OPTION = {'id': '', 'text': 'All'};

    pageData.registerUrl('hierarchy', 'hierarchy');
    pageData.registerUrl('group_filter', 'group_filter');

    beforeEach(function() {
        viewModel = hqImport("champ/js/knockout/prevision_vs_achievement_graph").model();

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
        clienttypes = [
            ALL_OPTION,
            {id: 'fsw_ct1', value: 'ct1', parent_id: 'cbo1'},
            {id: 'msm_ct2', value: 'ct2', parent_id: 'cbo1'},
            {id: 'fsw_ct3', value: 'ct3', parent_id: 'cbo2'},
            {id: 'fsw_ct4', value: 'ct4', parent_id: 'cbo2'},
            {id: 'msm_ct5', value: 'ct5', parent_id: 'cbo3'},
            {id: 'msm_ct6', value: 'ct6', parent_id: 'cbo3'},
            {id: 'msm_ct7', value: 'ct7', parent_id: 'cbo4'},
            {id: 'msm_ct8', value: 'ct8', parent_id: 'cbo4'},
        ];
        userpls = [
            ALL_OPTION,
            {id: 'userpl1', value: 'userpl1', parent_id: 'fsw_ct1'},
            {id: 'userpl2', value: 'userpl2', parent_id: 'fsw_ct1'},
            {id: 'userpl3', value: 'userpl3', parent_id: 'msm_ct2'},
            {id: 'userpl4', value: 'userpl4', parent_id: 'msm_ct2'},
            {id: 'userpl5', value: 'userpl5', parent_id: 'fsw_ct3'},
            {id: 'userpl6', value: 'userpl6', parent_id: 'fsw_ct3'},
            {id: 'userpl7', value: 'userpl7', parent_id: 'fsw_ct4'},
            {id: 'userpl8', value: 'userpl8', parent_id: 'fsw_ct4'},
            {id: 'userpl9', value: 'userpl9', parent_id: 'msm_ct7'},
            {id: 'userpl10', value: 'userpl10', parent_id: 'msm_ct7'},
            {id: 'userpl11', value: 'userpl11', parent_id: 'msm_ct8'},
            {id: 'userpl12', value: 'userpl12', parent_id: 'msm_ct8'},
        ];

        viewModel.districts = districts;
        viewModel.cbos = cbos;
        viewModel.userpls = userpls;
        viewModel.clienttypes = clienttypes;
        viewModel.availableDistricts(districts);
        viewModel.availableCbos(cbos);
        viewModel.availableUserpls(userpls);
    });

    it('test districtOnSelect only district selected', function() {
        var event = {
            added: {id: 'district1', value: 'district1'},
        };
        assert.equal(3, viewModel.availableDistricts().length);
        assert.equal(5, viewModel.availableCbos().length);
        assert.equal(13, viewModel.availableUserpls().length);
        viewModel.filters.target_district(['district1']);
        viewModel.districtOnSelect(event);
        assert.equal(3, viewModel.availableCbos().length);
        assert.equal(9, viewModel.availableUserpls().length);
    });

    it('test districtOnSelect all option', function() {
        var event = {
            added: ALL_OPTION,
        };
        assert.equal(3, viewModel.availableDistricts().length);
        assert.equal(5, viewModel.availableCbos().length);
        assert.equal(13, viewModel.availableUserpls().length);
        viewModel.filters.target_district(['']);
        viewModel.districtOnSelect(event);
        assert.equal(5, viewModel.availableCbos().length);
        assert.equal(13, viewModel.availableUserpls().length);
    });

    it('test cboOnSelect only cbo selected', function() {
        var event = {
            added: {id: 'cbo1', value: 'cbo1', parent_id: 'district1'},
        };
        assert.equal(5, viewModel.availableCbos().length);
        assert.equal(13, viewModel.availableUserpls().length);
        viewModel.filters.target_cbo(['cbo1']);
        viewModel.cboOnSelect(event);
        assert.equal(5, viewModel.availableUserpls().length);
    });

    it('test cboOnSelect all option', function() {
        var event = {
            added: ALL_OPTION,
        };
        assert.equal(5, viewModel.availableCbos().length);
        assert.equal(13, viewModel.availableUserpls().length);
        viewModel.filters.target_cbo(['']);
        viewModel.cboOnSelect(event);
        assert.equal(13, viewModel.availableUserpls().length);
    });

    it('test cboOnSelect district and cbo selected', function() {
        var event = {
            added: {id: 'cbo1', value: 'cbo1', parent_id: 'district1'},
        };
        assert.equal(5, viewModel.availableCbos().length);
        assert.equal(13, viewModel.availableUserpls().length);
        viewModel.filters.target_district(['district1']);
        viewModel.filters.target_cbo(['cbo1']);
        viewModel.cboOnSelect(event);
        assert.equal(5, viewModel.availableUserpls().length);
    });

    it('test clienttypeOnSelect only client type selected', function() {
        var event = {
            added: {id: 'fsw', value: 'fsw'},
        };
        assert.equal(13, viewModel.availableUserpls().length);
        viewModel.filters.target_clienttype(['fsw']);
        viewModel.clienttypeOnSelect(event);
        assert.equal(7, viewModel.availableUserpls().length);
    });

    it('test clienttypeOnSelect all option selected', function() {
        var event = {
            added: ALL_OPTION,
        };
        assert.equal(13, viewModel.availableUserpls().length);
        viewModel.filters.target_clienttype(['']);
        viewModel.clienttypeOnSelect(event);
        assert.equal(13, viewModel.availableUserpls().length);
    });

    it('test clienttypeOnSelect cbo and clienttype selected', function() {
        var event = {
            added: ALL_OPTION,
        };
        assert.equal(13, viewModel.availableUserpls().length);
        viewModel.filters.target_cbo(['cbo1']);
        viewModel.filters.target_clienttype(['fsw']);
        viewModel.clienttypeOnSelect(event);
        assert.equal(5, viewModel.availableUserpls().length);
    });

    it('test clienttypeOnSelect district, cbos and clienttype selected', function() {
        var event = {
            added: ALL_OPTION,
        };
        assert.equal(13, viewModel.availableUserpls().length);
        viewModel.filters.target_district(['district1']);
        viewModel.filters.target_cbo(['cbo1', 'cbo2']);
        viewModel.filters.target_clienttype(['fsw']);
        viewModel.clienttypeOnSelect(event);
        assert.equal(9, viewModel.availableUserpls().length);
    });

    it('test onSelectOption', function() {
        var event = {
            added: ALL_OPTION,
        };
        viewModel.filters.kp_prev_client_type(['fsw', 'msm']);
        viewModel.onSelectOption(event, 'kp_prev_client_type');
        assert.deepEqual([''], viewModel.filters.kp_prev_client_type());
    });
});
