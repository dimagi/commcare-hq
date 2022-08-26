describe('Formplayer utils', function () {
    var Fixtures = hqImport("cloudcare/js/form_entry/spec/fixtures"),
        UI = hqImport("cloudcare/js/form_entry/form_ui"),
        Utils = hqImport("cloudcare/js/form_entry/utils");

    it('Should determine if two answers are equal', function () {
        var answersEqual = Utils.answersEqual,
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

    it('Should get root form for questions', function () {
        /**
         *  Form's question tree:
         *     text
         *     group
         *         textInGroup
         *     repeat
         *         groupInRepeat
         *             textInRepeat
         */
        var text = Fixtures.textJSON({ix: "0"}),
            textInGroup = Fixtures.textJSON({ix: "1,0"}),
            group = Fixtures.groupJSON({ix: "1", children: [textInGroup]}),
            textInRepeat = Fixtures.textJSON({ix: "2_0,0"}),
            groupInRepeat = Fixtures.groupJSON({ix: "2_0", children: [textInRepeat]}),
            repeat = Fixtures.repeatJSON({ix: "2", children: [groupInRepeat]}),
            form = UI.Form({
                tree: [text, group, repeat],
            });

        [text, group, repeat] = form.children();
        [groupInRepeat] = repeat.children();
        [textInRepeat] = groupInRepeat.children();

        assert.equal(Utils.getRootForm(text), form);
        assert.equal(Utils.getRootForm(groupInRepeat), form);
        assert.equal(Utils.getRootForm(textInRepeat), form);

        assert.equal(Utils.getBroadcastContainer(text), form);
        assert.equal(Utils.getBroadcastContainer(textInRepeat), groupInRepeat);
    });
});
