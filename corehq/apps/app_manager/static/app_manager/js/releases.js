function SavedApp(o) {
    var self = ko.mapping.fromJS(o);
    $.each(['comment_user_name', '_deleteState'], function (i, attr) {
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
    self.buildState = ko.observable('');
    self.fetchState = ko.observable('');
    self.nextVersionToFetch = null;
    self.fetchLimit = 5;
    self.deployAnyway = {};
    self.appVersion = ko.observable(self.options.appVersion);
    self.lastAppVersion = ko.observable();
    self.savedApps.subscribe(function () {
        var lastApp = self.savedApps()[0];
        self.lastAppVersion(lastApp ? lastApp.version() : -1);
    });
    self.url = function (name) {
        var template = self.options.urls[name];
        for (var i = 1; i < arguments.length; i++) {
            template = template.replace('___', ko.utils.unwrapObservable(arguments[i]));
        }
        return template;
    };
    self.latestReleaseId = ko.computed(function () {
        for (var i = 0; i < self.savedApps().length; i++) {
            var savedApp = self.savedApps()[i];
            if (savedApp.is_released()) {
                return savedApp.id();
            }
        }
    });
    self.addSavedApp = function (savedApp, toBeginning) {
        if (toBeginning) {
            self.savedApps.unshift(savedApp);
        } else {
            self.savedApps.push(savedApp);
        }
        self.deployAnyway[savedApp.id()] = ko.observable(false);
    };
    self.getMoreSavedApps = function () {
        self.fetchState('pending');
        $.ajax({
            url: self.url('fetch'),
            dataType: 'json',
            data: {
                start_build: self.nextVersionToFetch,
                limit: self.fetchLimit
            }
        }).success(function (savedApps) {
            var i, savedApp;
            for (i = 0; i < savedApps.length; i++) {
                savedApp = SavedApp(savedApps[i]);
                self.addSavedApp(savedApp);
            }
            if (i) {
                self.nextVersionToFetch = savedApps[i-1].version - 1;
            }
            if (savedApps.length < self.fetchLimit) {
                self.doneFetching(true);
            } else {
                self.doneFetching(false);
            }
            self.fetchState('');
        }).error(function () {
            self.fetchState('error');
        });
    };
    self.toggleRelease = function (savedApp) {
        var is_released = savedApp.is_released();
        var saved_app_id = savedApp.id();
        if (savedApp.is_released() !== 'pending') {
            var url = self.url('release', saved_app_id);
            var that = this;
            $.ajax({
                url: url,
                type: 'post',
                dataType: 'json',
                data: {ajax: true, is_released: !is_released},
                beforeSend: function () {
                    savedApp.is_released('pending');
                },
                success: function (data) {
                    savedApp.is_released(data.is_released);
                },
                error: function () {
                    savedApp.is_released('error');
                }
            });
        }
    };
    self.deleteSavedApp = function (savedApp) {
        savedApp._deleteState('pending');
        $.post(self.url('delete'), {saved_app: savedApp.id()}, function () {
            self.savedApps.remove(savedApp);
            savedApp._deleteState(false);
        }).error(function () {
            savedApp._deleteState('error');
            alert(
                "Sorry, that didn't go through. Please reload your page " +
                "and try again"
            );
        });
    };
    self.revertSavedApp = function (savedApp) {
        $.postGo(self.url('revertBuild'), {saved_app: savedApp.id()});
    };
    self.makeNewBuildEnabled = function () {
        if (self.buildState() === 'pending') {
            return false;
        } else if (self.lastAppVersion() === undefined) {
            return self.doneFetching();
        } else {
            return self.lastAppVersion() !== self.appVersion();
        }
    };
    self.makeNewBuild = function () {
        var comment = window.prompt("Please write a comment about the build you're making to help you remember later:");
        if (comment || comment === "") {
            $(this).find("input[name='comment']").val(comment);
        } else {
            return;
        }
        self.buildState('pending');
        $.post(self.url('newBuild'), {
            comment: comment
        }).success(function (data) {
                $('#build-errors-wrapper').html(data.error_html);
                if (data.saved_app) {
                    self.addSavedApp(SavedApp(data.saved_app), true);
                }
                self.buildState('');
            }).error(function () {
                self.buildState('error');
            });
    };
    self.group_deploy = function() { 
        var json_contacts = $('.tabbable').find("input[name]='recipients'").attr("data-contacts").replace(/'/g,'"');
        $('.tabbable').find("input[name]='recipients'").multiTypeahead({ 
            source: jQuery.parseJSON(json_contacts),
        }).focus();
    };
    // init
    setTimeout(function () {
        self.getMoreSavedApps();
    }, 0);
}