/* eslint-env mocha */
/* global Backbone */
hqDefine("cloudcare/js/formplayer/spec/controller_spec", function () {
    describe('Controller', function () {

        describe('groupDisplays', function () {
            const controller = hqImport("cloudcare/js/formplayer/menus/controller");

            const grouped = controller.groupDisplays([]);

            assert.deepEqual([1], grouped);
            assert.false(true);
        });
    });
});
