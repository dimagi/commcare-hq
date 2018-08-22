hqDefine("users/js/mobile_workers", function() {
    var mobileWorkersList = function() {
        var self = {};
        self.users = ko.observableArray([]);

        self.goToPage = function(page) {
            self.users.removeAll();

            $.ajax({
                method: 'GET',
                url: hqImport("hqwebapp/js/initial_page_data").reverse('paginate_mobile_workers'),
                data: {
                    page: page || 1,
                    query: '',  // TODO
                    limit: 10,  // TODO
                },
                success: function(data) {
                    self.users.removeAll();     // just in case there are multiple goToPage calls simultaneously
                    _.each(data.users, function(user) {
                        self.users.push(user);
                    });
                },
                error: function() {
                    // TODO: something generic
               },
            });
        };

        self.goToPage(1);

        return self;
    };

    $(function() {
        $("#mobile-workers-list").koApplyBindings(mobileWorkersList());
    });
});
