hqDefine('builds/js/edit-builds', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    var doc = initialPageData.get('doc'),
        pretty_doc = JSON.stringify(doc, undefined, 2);

    function Version(version, label, superuser_only, j2me_enabled) {
        var self = this;
        self.version = ko.observable(version);
        self.label = ko.observable(label);
        self.superuser_only = ko.observable(superuser_only);
        self.j2me_enabled = ko.observable(j2me_enabled);

        // subscribe for change in version to update j2me_enabled
        // property and hence the checkbox in view
        self.version.subscribe(function(newValue){
            self.j2me_enabled(buildsMenu.j2me_enabled_versions.
                              includes(newValue)
                             );
        })
    }

    function Menu() {
        var self = this;

        self.available_versions = initialPageData.get('available_versions');
        self.j2me_enabled_versions = initialPageData.get('j2me_enabled_versions');
        self.versions = ko.observableArray([])
        self.available_ones = [];
        self.available_twos = [];
        self.default_one = ko.observable();
        self.default_two = ko.observable();

        self.addVersion = function() {
            self.versions.push(new Version('', '', false));
        };
        self.removeVersion = function(version) { self.versions.remove(version) };

        _.each(doc.menu, function(version) {
            self.versions.push(new Version(
                version.build.version, version.label,
                version.superuser_only, version.j2me_enabled
            ));
        });
        _.each(doc.defaults, function(version_doc) {
            var version = version_doc.version;
            if (version[0] === '1') {
                self.default_one(version);
            } else if (version[0] === '2') {
                self.default_two(version);
            }
        });
        _.each(self.available_versions, function(version) {
            if (version[0] === '1') {
                self.available_ones.push(version);
            } else if (version[0] === '2') {
                self.available_twos.push(version);
            }
        });
    }

    function outputJSON(menu) {
        doc.menu = [];
        _.each(menu.versions(), function(version) {
            doc.menu.push({
                'j2me_enabled': version.j2me_enabled(),
                'superuser_only': version.superuser_only(),
                'label': version.label(),
                'build': {
                    'version': version.version(),
                    'build_number': null,
                    'latest': true
                }
            });
        });
        doc.defaults = [];
        _.each([menu.default_one, menu.default_two], function(deflt) {
            doc.defaults.push(
                {
                'version': deflt(),
                'build_number': null,
                'latest': true
                }
            )
        });
        return doc
    }

    var buildsMenu = new Menu();
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

    $('#menu-form .btn-primary').click(function(e) {
        var response = postGo(
            $('#menu-form')[0].action,
            {'doc': JSON.stringify(outputJSON(buildsMenu))}
        );
    });
});
