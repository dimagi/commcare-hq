describe('choiceListUtils', function() {
    it('Correctly formats select2 data', function() {
        result = choiceListUtils.formatPageForSelect2([
            {
                value: '123',
                display: 'Ben'
            },
            {
                value: '456',
                display: null
            }
        ]);
        assert(result, [
            {
                id: '123',
                text: 'Ben'
            },
            {
                id: '456',
                text: ''
            }
        ]);
    });
});

