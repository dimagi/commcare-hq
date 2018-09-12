hqDefine("data_interfaces/js/find_by_id", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    initialPageData
) {
    var findModel = function () {
        var self = {};
        self.placeholder = gettext('Form Submission ID');
        self.query = ko.observable('');
        self.error = ko.observable('');
        self.link = ko.observable('');
        self.loading = ko.observable(false);

        self.linkMessage = ko.computed(function () {
            return self.link() ? _.template("Form submission found! <a href='<%= link %>'>Click here</a> if you are not redirected.")({link: self.link()}) : "";
        });

        self.allowFind = ko.computed(function () {
            return self.query() && !self.loading();
        });

        self.find = function () {
            self.loading(true);
            self.link('');
            self.error('');
            $.ajax({
                method: 'GET',
                url: initialPageData.reverse('global_quick_find'),
                data: {
                    q: self.query(),
                    redirect: 'false',
                },
                success: function (data) {
                    self.loading(false);
                    self.link(data.link);
                    _.delay(function () {
                        document.location = data.link;
                    }, 2000);
                },
                error: function () {
                    self.loading(false);
                    self.error(gettext('Could not find form submission'));
                },
            });
        };

        return self;
    };

    $(function () {
        $("#find-form").koApplyBindings(findModel());
    });
});
