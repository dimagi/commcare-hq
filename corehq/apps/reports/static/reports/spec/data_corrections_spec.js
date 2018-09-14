/* eslint-env mocha */

describe('Data Corrections', function () {
    var $fixture = $("#data-corrections-fixture").remove(),
        thingList = function (count) {
            // Generate a list "thing01, thing02, ..." from 1 to count, with
            // numbers properly zero-padded so they sort
            var logCount = Math.log10(count);
            return _.map(_.range(count), function (n) {
                n = n + 1;
                var zeroes = _.map(_.range(logCount - Math.log10(n)), function () { return "0"; }).join("");
                return "thing" + zeroes + n;
            });
        },
        generateOptions = function (properties) {
            return {
                saveUrl: '',
                properties: properties,
                propertyNames: _.sortBy(_.keys(properties)),
            };
        },
        openModal = function () {
            $(".data-corrections-trigger").click();
        },
        closeModal = function () {
            $(".data-corrections-modal .close").click();
        },
        updateProperty = function (name, newValue) {
            $(".data-corrections-modal [data-name='" + name + "']").val(newValue).change();
        },
        search = function (query) {
            $(".data-corrections-modal .modal-header input").val(query).change();
        },
        assertProperty = function (name, value) {
            assert.equal($(".data-corrections-modal [data-name='" + name + "']").val(), value);
        },
        assertVisibleProperties = function (expected) {
            assert.sameMembers(expected, _.map($(".data-corrections-modal .modal-body .form-group input:visible"), function (i) { return $(i).data("name"); }));
        },
        initModel = function (properties, additionalOptions) {
            additionalOptions = additionalOptions || {};
            return hqImport('reports/js/data_corrections').init(
                $(".data-corrections-trigger"),
                $(".data-corrections-modal"),
                _.extend(generateOptions(properties), additionalOptions)
            );
        };

    beforeEach(function () {
        var $clone = $fixture.clone();
        $clone.find(".modal").data("backdrop", 0);
        $("#mocha-sandbox").append($clone);
    });

    afterEach(function () {
        $("#mocha-sandbox").empty();
    });

    describe('Modal', function () {
        it('should appear on trigger and disappear on close', function () {
            initModel({ 'name': 'value' });
            var $modal = $(".data-corrections-modal");
            assert(!$modal.is(":visible"));
            openModal();
            assert($modal.is(":visible"));
            closeModal();
            assert(!$modal.is(":visible"));
        });

        it('should reset properties on close and re-open', function () {
            initModel({
                'black': 'darjeeling',
                'green': 'genmaicha',
                'white': 'silver needle',
            });
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

    describe('Inside modal', function () {
        it('should search by property name', function () {
            initModel({
                'black': 'darjeeling',
                'green': 'genmaicha',
                'white': 'silver needle',
            });
            openModal();

            search("green");
            assertVisibleProperties(["green"]);
            search("");
            assertVisibleProperties(["black", "green", "white"]);
            search("xyz");
            assertVisibleProperties([]);
        });

        it('should display multiple pages when there are many properties', function () {
            var itemCount = 100,
                names = thingList(itemCount),
                model = initModel(_.object(names, names));
            openModal();

            assert.equal(model.totalPages(), Math.ceil(itemCount / model.itemsPerPage()));
            assertVisibleProperties(names.slice(0, model.itemsPerPage()));

            model.currentPage(model.totalPages());
            assertVisibleProperties(names.slice((model.totalPages() - 1) * model.itemsPerPage()));
        });

        it('should search across multiple pages', function () {
            var names = thingList(100);
            initModel(_.object(names, names));
            openModal();
            search("10");
            assertVisibleProperties(["thing010", "thing100"]);
        });

        it('should display multiple attributes of each property', function () {
            var model = initModel({
                red: {
                    value: 'ff0000',
                    spanish: 'rojo',
                    french: 'rouge',
                },
                orange: {
                    value: 'ff6600',
                    spanish: 'anaranjado',
                    french: 'orange',
                },
                yellow: {
                    value: 'ffff00',
                    spanish: 'amarillo',
                    french: 'jaune',
                },
            }, {
                displayProperties: [{
                    property: 'name',
                    name: 'English',
                }, {
                    property: 'spanish',
                    name: 'Spanish',
                }, {
                    property: 'french',
                    name: 'French',
                    search: 'spanish',
                }],
                propertyPrefix: "<div class='test-property'>",
                propertySuffix: "</div>",
            });
            openModal();

            var assertVisibleText = function (expected) {
                assert.sameMembers(expected, _.map($(".data-corrections-modal .test-property:visible"), function (p) { return p.innerText; }));
            };

            assert($(".data-corrections-modal .nav > :first-child").hasClass("active"), "Should display first property by default");

            // Display and search english values
            model.updateDisplayProperty("name");
            assertVisibleText(["orange", "red", "yellow"]);
            search("yellow");
            assertVisibleProperties(["yellow"]);

            // Display and search spanish values
            model.updateDisplayProperty("spanish");
            assertVisibleText(["anaranjado", "rojo", "amarillo"]);
            search("rojo");
            assertVisibleProperties(["red"]);
        });
    });
});
