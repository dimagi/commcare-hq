"use strict";
hqDefine('builds/js/bootstrap5/edit_builds', [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function ($, _, ko, initialPageData) {
    var doc = initialPageData.get('doc');

    function versionModel(version, label, superuserOnly) {
        var self = {};
        self.version = ko.observable(version);
        self.label = ko.observable(label);
        self.superuser_only = ko.observable(superuserOnly);

        return self;
    }

    function menuModel() {
        var self = {};

        self.available_versions = initialPageData.get('available_versions');
        self.versions = ko.observableArray([]);
        self.available_ones = [];
        self.available_twos = [];
        self.default_one = ko.observable();
        self.default_two = ko.observable();

        self.addVersion = function () {
            self.versions.push(versionModel('', '', false));
        };
        self.removeVersion = function (version) { self.versions.remove(version); };

        _.each(doc.menu, function (version) {
            self.versions.push(versionModel(
                version.build.version, version.label
            ));
        });
        _.each(doc.defaults, function (versionDoc) {
            var version = versionDoc.version;
            if (version[0] === '1') {
                self.default_one(version);
            } else if (version[0] === '2') {
                self.default_two(version);
            }
        });
        _.each(self.available_versions, function (version) {
            if (version[0] === '1') {
                self.available_ones.push(version);
            } else if (version[0] === '2') {
                self.available_twos.push(version);
            }
        });

        return self;
    }

    function outputJSON(menu) {
        doc.menu = [];
        _.each(menu.versions(), function (version) {
            doc.menu.push({
                'superuser_only': version.superuser_only(),
                'label': version.label(),
                'build': {
                    'version': version.version(),
                    'build_number': null,
                    'latest': true,
                },
            });
        });
        doc.defaults = [];
        _.each([menu.default_one, menu.default_two], function (deflt) {
            doc.defaults.push({
                'version': deflt(),
                'build_number': null,
                'latest': true,
            });
        });
        return doc;
    }

    var buildsMenu = menuModel();
    $("#menu-form").koApplyBindings(buildsMenu);

    function postGo(url, params) {
        var $form = $("#submit-menu-form")
            .attr("action", url);
        $.each(params, function (name, value) {
            $("<input type='hidden'>")
                .attr("name", name)
                .attr("value", value)
                .appendTo($form);
        });
        $form.submit();
    }

    $('#menu-form .btn-primary').click(function () {
        postGo(
            $('#menu-form')[0].action,
            {'doc': JSON.stringify(outputJSON(buildsMenu))}
        );
    });
});
