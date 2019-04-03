hqDefine('domain/js/toggles', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/alert_user',
    'hqwebapp/js/main',
], function (
    $,
    ko,
    _,
    initialPageData,
    alertUser
) {

    var Toggle = function (data) {
        var self = {};
        self.slug = data['slug'];
        self.label = data['label'];
        self.description = data['description'];
        self.helpLink = data['help_link'];
        self.tag = data['tag'];
        self.tagCssClass = data['tag_css_class'];
        self.domainEnabled = ko.observable(data['domain_enabled']);
        self.userEnabled = ko.observable(data['user_enabled']);
        self.hasDomainNamespace = data['has_domain_namespace'];

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
    ko.applyBindings({"toggles": allToggles}, $("#toggles-table")[0]);
});
