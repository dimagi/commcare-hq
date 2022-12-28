hqDefine("cloudcare/js/form_entry/spec/utils_spec", [
    "hqwebapp/js/initial_page_data",
    "cloudcare/js/form_entry/spec/fixtures",
    "cloudcare/js/form_entry/form_ui",
    "cloudcare/js/form_entry/utils",
], function (
    initialPageData,
    fixtures,
    formUI,
    utils,
) {
    describe('Formplayer utils', function () {
        it('Should determine if two answers are equal', function () {
            var answersEqual = utils.answersEqual,
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
            initialPageData.register("toggles_dict", { WEB_APPS_ANCHORED_SUBMIT: false });
            var text = fixtures.textJSON({ix: "0"}),
                textInGroup = fixtures.textJSON({ix: "1,0"}),
                group = fixtures.groupJSON({ix: "1", children: [textInGroup]}),
                textInRepeat = fixtures.textJSON({ix: "2_0,0"}),
                groupInRepeat = fixtures.groupJSON({ix: "2_0", children: [textInRepeat]}),
                repeat = fixtures.repeatJSON({ix: "2", children: [groupInRepeat]}),
                form = formUI.Form({
                    tree: [text, group, repeat],
                });

            [text, group, repeat] = form.children();
            [groupInRepeat] = repeat.children();
            [textInRepeat] = groupInRepeat.children();

            assert.equal(groupInRepeat.children()[0].caption(), null);
            assert.equal(utils.getRootForm(text), form);
            assert.equal(utils.getRootForm(groupInRepeat), form);
            assert.equal(utils.getRootForm(textInRepeat), form);

            assert.equal(utils.getBroadcastContainer(text), form);
            assert.equal(utils.getBroadcastContainer(textInRepeat), groupInRepeat);

            initialPageData.unregister("toggles_dict");
        });
    });
});
