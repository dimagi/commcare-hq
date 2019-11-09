hqDefine('app_manager/js/multimedia_size_util',[
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function ($, _, ko, initialPageData) {
    var multimediaSize = function (name, size) {
        var self = {};
        self.name = ko.observable(name);
        self.size = ko.observable(size);
        return self;
    }
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
                    _.each(content, function(mmsize, mmType) {
                        self.sizes.push(multimediaSize(mmType, mmsize));
                    });
                    self.load_state('loaded');
                },
                error: function (data) {
                    if (data.hasOwnProperty('responseJSON')) {
                        alert(data.responseJSON.message);
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
    }
});
