function SavedApp(o) {
    var self = ko.mapping.fromJS(o);
    $.each(['comment_user_name'], function (i, attr) {
        self[attr] = self[attr] || ko.observable();
    });
    return self;
}

function ReleasesMain(o) {
    /* {fetchUrl} */
    var self = this;
    self.savedApps = ko.observableArray();
    self.doneFetching = ko.observable(false);
    self.nextVersionToFetch = null;
    self.fetchLimit = 5;
    self.getMoreSavedApps = function () {
        $.ajax({
            url: o.fetchUrl,
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
    self.getMoreSavedApps();
}