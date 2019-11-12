hqDefine('app_manager/js/multimedia_size_util',[
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/alert_user',
], function ($, _, ko, alertUser) {
    var multimediaSize = function (name, size) {
        var self = {};
        self.name = ko.observable(name);
        self.size = ko.observable(size);
        return self;
    };
    var multimediaSizesView = function (url) {
        var self = {};
        self.sizes = ko.observableArray();
        self.load_state = ko.observable(null);
        self.showSpinner = ko.observable(false);
        self.load = function () {
            self.load_state('loading');
            $.ajax({
                url: url,
                success: function (content) {
                    self.sizes(_.map(content, function (mmsize, mmType) {
                        return multimediaSize(mmType, mmsize)
                    }));
                    self.loadState('loaded');
                },
                error: function (data) {
                    if (data.hasOwnProperty('responseJSON')) {
                        alertUser.alert_user(data.responseJSON.message, "danger");
                    }
                    else {
                        alert(gettext('Oops, there was a problem loading this section. Please try again.'));
                    }
                    self.load_state('error');
                },
            });
        };
        return self;
    };
    return {
        multimediaSizesView: multimediaSizesView,
    };
});
