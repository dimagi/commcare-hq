function SavedApp(o) {
    var self = ko.mapping.fromJS(o);
    $.each(['comment_user_name'], function (i, attr) {
        self[attr] = self[attr] || ko.observable();
    });
    return self;
}

function ReleasesMain(o) {
    /* {fetchUrl, deleteUrl} */
    var self = this;
    self.options = o;
    self.users_cannot_share = self.options.users_cannot_share;
    self.savedApps = ko.observableArray();
    self.doneFetching = ko.observable(false);
    self.nextVersionToFetch = null;
    self.fetchLimit = 5;
    self.url = function (name) {
        var template = self.options.urls[name];
        for (var i = 1; i < arguments.length; i++) {
            template = template.replace('___', ko.utils.unwrapObservable(arguments[i]));
        }
        return template;
    };
    self.getMoreSavedApps = function () {
        $.ajax({
            url: self.url('fetch'),
            dataType: 'json',
            data: {
                start_build: self.nextVersionToFetch,
                limit: self.fetchLimit
            }
        }).success(function (savedApps) {
            var i;
            for (i = 0; i < savedApps.length; i++) {
                self.savedApps.push(SavedApp(savedApps[i]));
            }
            if (i) {
                self.nextVersionToFetch = savedApps[i-1].version - 1;
            }
            if (savedApps.length < self.fetchLimit) {
                self.doneFetching(true);
            }
        });
    };
    self.deleteSavedApp = function (savedApp) {
        $.post(self.url('delete'), {saved_app: savedApp.id}, function () {
            self.savedApps.remove(savedApp);
        });
    };
    // init
    self.getMoreSavedApps();
}