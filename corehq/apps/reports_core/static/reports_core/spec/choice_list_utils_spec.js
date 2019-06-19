describe('choiceListUtils', function () {
    it('Correctly formats select2 data', function () {
        var result = hqImport('reports_core/js/choice_list_utils').formatPageForSelect2([
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
