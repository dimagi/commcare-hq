describe('Formplayer utils', function () {
    it('Should determine if two answers are equal', function () {
        var result;

        result = Formplayer.Utils.answersEqual('ben', 'bob');
        assert.isFalse(result);

        result = Formplayer.Utils.answersEqual('ben', 'ben');
        assert.isTrue(result);

        result = Formplayer.Utils.answersEqual(['b', 'e', 'n'], ['b', 'o', 'b']);
        assert.isFalse(result);

        result = Formplayer.Utils.answersEqual(['b', 'e', 'n'], ['b', 'e', 'n']);
        assert.isTrue(result);
    });
});
