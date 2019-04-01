hqDefine('domain/js/toggles', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/main',
], function (
    $,
    ko,
    _,
    initialPageData
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
        self.url = initialPageData.reverse('edit_toggle', self.slug);

        self.cssClass = ko.computed(function () {
            if (self.domainEnabled()) {
                return 'success';
            } else if (self.userEnabled()) {
                return 'info';
            }
        });

        return self;
    };

    var allToggles = _.map(initialPageData.get('toggles'), Toggle);
    ko.applyBindings({"toggles": allToggles}, $("#toggles-table")[0]);
});
