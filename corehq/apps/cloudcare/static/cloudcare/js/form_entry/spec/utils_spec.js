describe('Formplayer utils', function () {
    it('Should determine if two answers are equal', function () {
        var answersEqual = hqImport("cloudcare/js/form_entry/utils").answersEqual,
            result;

        result = answersEqual('ben', 'bob');
        assert.isFalse(result);

        result = answersEqual('ben', 'ben');
        assert.isTrue(result);

        result = answersEqual(['b', 'e', 'n'], ['b', 'o', 'b']);
        assert.isFalse(result);

        result = answersEqual(['b', 'e', 'n'], ['b', 'e', 'n']);
        assert.isTrue(result);
    });
});
