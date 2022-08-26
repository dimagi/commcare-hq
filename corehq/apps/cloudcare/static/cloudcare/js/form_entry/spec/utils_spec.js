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
         *         textInRepeat
         *         groupInRepeat
         *             textInNestedGroup
         */
        var text = Fixtures.textJSON({ix: "0"}),
            textInGroup = Fixtures.textJSON({ix: "1,0"}),
            group = Fixtures.groupJSON({ix: "1", children: [textInGroup]}),
            textInRepeat = Fixtures.textJSON({ix: "2,0"}),
            textInNestedGroup = Fixtures.textJSON({ix: "2,1,0"}),
            groupInRepeat = Fixtures.groupJSON({ix: "2,1", children: [textInNestedGroup]}),
            repeat = Fixtures.repeatJSON({ix: "2", children: [textInRepeat, groupInRepeat]}),
            form = UI.Form({
                tree: [text, group, repeat],
            });

        [text, group, repeat] = form.children();
        [textInRepeat, groupInRepeat] = repeat.children();
        [textInNestedGroup] = groupInRepeat.children();

        assert.equal(Utils.getRootContainer(text), form);
        assert.equal(Utils.getRootContainer(textInRepeat), form);
        assert.equal(Utils.getRootContainer(groupInRepeat), form);

        var repeatCallback = function (container) {
            return container instanceof UI.RepeatClass;
        }
        assert.equal(Utils.getRootContainer(text, repeatCallback), form);
        assert.equal(Utils.getRootContainer(textInRepeat, repeatCallback), repeat);
        assert.equal(Utils.getRootContainer(textInNestedGroup, repeatCallback), repeat);
    });
});
