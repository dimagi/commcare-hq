/* eslint-env mocha */
hqDefine("export/spec/Exports.Utils.spec", [
    'underscore',
    'export/js/const',
    'export/js/models',
    'export/js/utils',
], function (
    _,
    constants,
    models,
    utils
) {
    describe('Export Utility functions', function () {
        describe('#getTagCSSClass', function () {
            it('Should get regular tag class', function () {
                var cls = utils.getTagCSSClass('random-tag');
                assert.equal(cls, 'label label-default');
            });

            it('Should get warning tag class', function () {
                var cls = utils.getTagCSSClass(constants.TAG_DELETED);
                assert.equal(cls, 'label label-warning');
            });
        });

        describe('#readablePath', function () {
            it('Should convert an anrray of PathNode to a dot path', function () {
                var nodes = [
                    new models.PathNode({ name: 'form', is_repeat: false, doc_type: 'PathNode' }),
                    new models.PathNode({ name: 'photo', is_repeat: false, doc_type: 'PathNode' }),
                ];
                assert.equal(models.readablePath(nodes), 'form.photo');
            });

            it('Should convert an array of PathNode to a dot path with repeats', function () {
                var nodes = [
                    new models.PathNode({ name: 'form', is_repeat: false, doc_type: 'PathNode' }),
                    new models.PathNode({ name: 'repeat', is_repeat: true, doc_type: 'PathNode' }),
                ];
                assert.equal(models.readablePath(nodes), 'form.repeat[]');
            });
        });

        describe('#customPathToNodes', function () {
            it('Should convert a string path to PathNodes', function () {
                var customPath = 'form.photo';
                var nodes = models.customPathToNodes(customPath);

                assert.equal(nodes.length, 2);
                assert.isTrue(_.all(nodes, function (n) { return n instanceof models.PathNode; }));

                assert.equal(nodes[0].name(), 'form');
                assert.isFalse(nodes[0].is_repeat());

                assert.equal(nodes[1].name(), 'photo');
                assert.isFalse(nodes[1].is_repeat());
            });

            it('Should convert a string path to PathNodes with repeats', function () {
                var customPath = 'form.repeat[]';
                var nodes = models.customPathToNodes(customPath);

                assert.equal(nodes.length, 2);
                assert.isTrue(_.all(nodes, function (n) { return n instanceof models.PathNode; }));

                assert.equal(nodes[0].name(), 'form');
                assert.isFalse(nodes[0].is_repeat());

                assert.equal(nodes[1].name(), 'repeat');
                assert.isTrue(nodes[1].is_repeat());
            });
        });
    });
});
