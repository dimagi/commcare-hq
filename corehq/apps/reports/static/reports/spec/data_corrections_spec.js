/* eslint-env mocha */

describe('Data Corrections', function () {
    var $fixture = $("#data-corrections-fixture").remove(),
        options = {
            saveUrl: '',
            properties: {
                'black': 'darjeeling',
                'green': 'genmaicha',
                'white': 'silver needle',
            },
            propertyNames: ['black', 'green', 'white'],
        },
        openModal = function() {
            $(".data-corrections-trigger").click();
        },
        closeModal = function() {
            $(".data-corrections-modal .close").click();
        },
        updateProperty = function(name, newValue) {
            $(".data-corrections-modal [data-name='" + name + "']").val(newValue).change();
        },
        assertProperty = function(name, value) {
            assert.equal($(".data-corrections-modal [data-name='" + name + "']").val(), value);
        },
        initModel = function(options) {
            return hqImport('reports/js/data_corrections').init(
                $(".data-corrections-trigger"),
                $(".data-corrections-modal"),
                options
            );
        };

    beforeEach(function() {
        $("#mocha-sandbox").append($fixture.clone());
    });

    afterEach(function() {
        $("#mocha-sandbox").empty();
    });

    describe('Modal', function () {
        it('should appear on trigger and disappear on close', function () {
            initModel(options);
            var $modal = $(".data-corrections-modal");
            assert(!$modal.is(":visible"));
            openModal();
            assert($modal.is(":visible"));
            closeModal();
            assert(!$modal.is(":visible"));
        });

        it('should reset properties on close and re-open', function () {
            var model = initModel(options);
            openModal();
            assertProperty("green", "genmaicha");
            updateProperty("green", "gunpowder");
            assertProperty("green", "gunpowder");
            closeModal();
            openModal();
            assertProperty("green", "genmaicha");
            closeModal();
        });
    });

    describe('Inside modal', function() {
        beforeEach(function() {
            hqImport('reports/js/data_corrections').init($trigger, $modal, options);
            $trigger.click();
        });

        afterEach(function() {
            $close.click();
        });

        // TODO: search
        // TODO: paging
        // TODO: modal sizing
        // TODO: display multiple property attributes, search
    });
});
