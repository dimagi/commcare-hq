import utils from "reports_core/js/choice_list_utils";

describe('choiceListUtils', function () {
    it('Correctly formats select2 data', function () {
        var result = utils.formatPageForSelect2([
            {
                value: '123',
                display: 'Ben',
            },
            {
                value: '456',
                display: null,
            },
        ]);
        assert(result, [
            {
                id: '123',
                text: 'Ben',
            },
            {
                id: '456',
                text: '',
            },
        ]);
    });
});
