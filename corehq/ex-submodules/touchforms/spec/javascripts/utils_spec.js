describe('Formplayer utils', function() {
    it('Should determine if two answers are equal', function() {
        var result;

        result = Formplayer.Utils.answersEqual('ben', 'bob');
        expect(result).toBe(false);

        result = Formplayer.Utils.answersEqual('ben', 'ben');
        expect(result).toBe(true);

        result = Formplayer.Utils.answersEqual(['b', 'e', 'n'], ['b', 'o', 'b']);
        expect(result).toBe(false);

        result = Formplayer.Utils.answersEqual(['b', 'e', 'n'], ['b', 'e', 'n']);
        expect(result).toBe(true);
    });
});
