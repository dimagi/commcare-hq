"use strict";

var pageData = hqImport('hqwebapp/js/initial_page_data');

describe('PrecisionVsAchievementsTableModel', function() {
    var viewModel;

    var ALL_OPTION = {'id': '', 'text': 'All'};

    pageData.registerUrl('champ_pva_table', 'champ_pva_table');

    beforeEach(function() {
        viewModel = new PrecisionVsAchievementsTableModel();
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
