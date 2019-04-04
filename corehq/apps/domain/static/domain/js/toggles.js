hqDefine('domain/js/toggles', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/main',
], function (
    $,
    ko,
    _,
    initialPageData,
    alertUser,
    assertProperties
) {

    var Toggle = function (data) {
        assertProperties.assert(data, [
            'slug', 'label', 'description', 'help_link', 'tag', 'tag_css_class',
            'tag_description', 'domain_enabled', 'user_enabled',
            'has_domain_namespace',
        ]);

        var self = {};
        self.slug = data['slug'];
        self.label = data['label'];
        self.description = data['description'];
        self.helpLink = data['help_link'];
        self.tag = data['tag'];
        self.tagCssClass = data['tag_css_class'];
        self.tagDescription = data['tag_description'];
        self.domainEnabled = ko.observable(data['domain_enabled']);
        self.userEnabled = ko.observable(data['user_enabled']);
        self.hasDomainNamespace = data['has_domain_namespace'];

        self.expanded = ko.observable(false);
        self.showHideDescription = function () { self.expanded(!self.expanded()); };

        self.cssClass = ko.computed(function () {
            if (self.domainEnabled()) {
                return 'success';
            } else if (self.userEnabled()) {
                return 'info';
            }
        });

        self.setTogglePending = ko.observable(false);
        self.toggleEnabledState = function () {
            self.setTogglePending(true);
            var newState = !self.domainEnabled();
            $.ajax({
                method: 'POST',
                url: initialPageData.reverse('set_toggle', self.slug),
                data: {
                    item: initialPageData.get('domain'),
                    enabled: newState,
                    namespace: 'domain',
                },
                success: function () { self.domainEnabled(newState); },
                error: function () { alertUser.alert_user("Something went wrong", 'danger'); },
                complete: function () { self.setTogglePending(false); },
            });
        };

        return self;
    };

    var allToggles = _.map(initialPageData.get('toggles'), Toggle);
    $("#toggles-table").koApplyBindings({"toggles": allToggles});
});
