/* eslint-env mocha */

import $ from 'jquery';
import _ from 'underscore';
import 'hqwebapp/js/components/pagination';
import 'hqwebapp/js/components/search_box';
import dataCorrections from 'reports/js/bootstrap5/data_corrections';
import 'commcarehq';

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
            $(".data-corrections-modal .btn-close").click();
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
            return dataCorrections.init(
                $(".data-corrections-trigger"),
                $(".data-corrections-modal"),
                _.extend(generateOptions(properties), additionalOptions),
            );
        };

    beforeEach(function () {
        var $clone = $fixture.clone();
        $clone.find(".modal").attr("data-bs-backdrop", false);
        $("#mocha-sandbox").append($clone);
    });

    afterEach(function () {
        $("#mocha-sandbox").empty();
    });

    describe('Modal', function () {
        it('should appear on trigger and disappear on close', function (done) {
            initModel({ 'name': 'value' });
            var $modal = $(".data-corrections-modal");
            assert(!$modal.is(":visible"));
            $modal.one("shown.bs.modal", function () {
                assert($modal.is(":visible"));
                $modal.one("hidden.bs.modal", function () {
                    assert(!$modal.is(":visible"));
                    done();
                });
                closeModal();
            });
            openModal();
        });

        it('should reset properties on close and re-open', function (done) {
            initModel({
                'black': 'darjeeling',
                'green': 'genmaicha',
                'white': 'silver needle',
            });
            var $modal = $(".data-corrections-modal");
            $modal.one("shown.bs.modal", function () {
                assertProperty("green", "genmaicha");
                updateProperty("green", "gunpowder");
                assertProperty("green", "gunpowder");
                $modal.one("hidden.bs.modal", function () {
                    openModal();
                    assertProperty("green", "genmaicha");
                    done();
                });
                closeModal();
            });
            openModal();
        });
    });

    describe('Inside modal', function () {
        it('should search by property name', function (done) {
            initModel({
                'black': 'darjeeling',
                'green': 'genmaicha',
                'white': 'silver needle',
            });
            var $modal = $(".data-corrections-modal");
            $modal.one("shown.bs.modal", function () {
                search("green");
                assertVisibleProperties(["green"]);
                done();
            });
            openModal();
        });

        it('should search for a non-existent property', function (done) {
            initModel({
                'black': 'darjeeling',
                'green': 'genmaicha',
                'white': 'silver needle',
            });
            var $modal = $(".data-corrections-modal");
            $modal.one("shown.bs.modal", function () {
                search("xyz");
                assertVisibleProperties([]);
                done();
            });
            openModal();
        });

        it('should search for a blank string', function (done) {
            initModel({
                'black': 'darjeeling',
                'green': 'genmaicha',
                'white': 'silver needle',
            });
            openModal();

            _.defer(function () {
                search("");
                assertVisibleProperties(["black", "green", "white"]);
                done();
            });
        });

        it('should display multiple pages when there are many properties', function (done) {
            var itemCount = 100,
                names = thingList(itemCount),
                model = initModel(_.object(names, names));
            var $modal = $(".data-corrections-modal");
            $modal.one("shown.bs.modal", function () {
                assert.equal($(".pagination li").length - 2, Math.ceil(itemCount / model.itemsPerPage()));
                assertVisibleProperties(names.slice(0, model.itemsPerPage()));

                model.currentPage(model.totalItems());
                assertVisibleProperties(names.slice((model.totalItems() - 1) * model.itemsPerPage()));

                done();
            });
            openModal();
        });

        it('should search across multiple pages', function (done) {
            var names = thingList(100);
            initModel(_.object(names, names));
            var $modal = $(".data-corrections-modal");
            $modal.one("shown.bs.modal", function () {
                search("10");
                assertVisibleProperties(["thing010", "thing100"]);
                done();
            });
            openModal();
        });

        const multilingualProperties = {
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
        };
        const multilingualOptions = {
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
        };

        it('should display translated properties in default language', function (done) {
            var model = initModel(multilingualProperties, multilingualOptions);
            var assertVisibleText = function (expected) {
                assert.sameMembers(expected, _.map($(".data-corrections-modal .test-property:visible"), function (p) { return p.innerText; }));
            };

            var $modal = $(".data-corrections-modal");
            $modal.one("shown.bs.modal", function () {
                assert($(".data-corrections-modal .nav > :first-child").hasClass("active"), "Should display first property by default");
                model.updateDisplayProperty("name");
                assertVisibleText(["orange", "red", "yellow"]);
                search("yellow");
                assertVisibleProperties(["yellow"]);
                done();
            });
            openModal();
        });

        it('should display translated properties in non-default language', function (done) {
            var model = initModel(multilingualProperties, multilingualOptions);
            var assertVisibleText = function (expected) {
                assert.sameMembers(expected, _.map($(".data-corrections-modal .test-property:visible"), function (p) { return p.innerText; }));
            };

            var $modal = $(".data-corrections-modal");
            $modal.one("shown.bs.modal", function () {
                assert($(".data-corrections-modal .nav > :first-child").hasClass("active"), "Should display first property by default");
                model.updateDisplayProperty("spanish");
                assertVisibleText(["anaranjado", "rojo", "amarillo"]);
                search("rojo");
                assertVisibleProperties(["red"]);
                done();
            });
            openModal();
        });
    });
});
