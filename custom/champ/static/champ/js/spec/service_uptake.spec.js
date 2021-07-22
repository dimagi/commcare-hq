"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');

describe('ServiceUptakeModel', function() {
    var viewModel;

    var ALL_OPTION = {'id': '', 'text': 'All'};

    pageData.registerUrl('service_uptake', 'service_uptake');
    pageData.registerUrl('champ_pva', 'champ_pva');

    beforeEach(function() {
        viewModel = hqImport("champ/js/knockout/service_uptake").model();
    });

    it('test onSelectOption', function() {
        var event = {
            added: ALL_OPTION,
        };
        viewModel.filters.client_type(['fsw', 'msm']);
        viewModel.onSelectOption(event, 'client_type');
        assert.deepEqual([''], viewModel.filters.client_type());
    });
});
