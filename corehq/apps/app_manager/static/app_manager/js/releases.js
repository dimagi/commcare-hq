function SavedApp(o, r) {
    var $root = r;
    var self = ko.mapping.fromJS(o);
    $.each(['comment_user_name', '_deleteState'], function (i, attr) {
        self[attr] = self[attr] || ko.observable();
    });
    if (!self.include_media) {
        self.include_media = ko.observable(false);
    }
    self.get_short_odk_url = ko.computed(function() {
        if (self.include_media()) {
           if (self.short_odk_media_url) {
               return self.short_odk_media_url();
           }
        } else {
            if (self.short_odk_url) {
                return self.short_odk_url();
            }
        }
        return false;
    });

    self.get_short_odk_url_phonetic = ko.computed(function () {
        return app_manager_utils.bitly_nato_phonetic(self.get_short_odk_url());
    });

    self.allow_media_install = ko.computed(function(){
        return self.doc_type() !== "RemoteApp";  // remote apps don't support multimedia
    });

    self.mm_supported = function() {
        // This is added to fix legacy issues with incorrectly formatted media_profile.ccpr files.
        // Files that were generated prior to 10/16/2013 are affected, so don't support remote mm for build made before then.
        var supported_date = new Date(2013, 9, 16);
        var date_built = new Date(self.built_on());
        return date_built.getTime() > supported_date.getTime();
    };

    self.get_odk_install_url = ko.computed(function() {
        var slug = self.include_media() ? 'odk_media' : 'odk';
        return $root.url(slug, self.id());
    });

    self.sms_url = function(index) {
        if (index === 0) { // sending to sms
            return self.short_url();
        } else { // sending to odk
            if (self.include_media() && self.short_odk_media_url()) {
                return self.short_odk_media_url();
            } else {
                return self.short_odk_url();
            }
        }
    };

    self.editing_comment = ko.observable(false);
    self.new_comment = ko.observable(self.build_comment());
    self.pending_comment_update = ko.observable(false);
    self.comment_update_error = ko.observable(false);

    self.submit_new_comment = function () {
        self.pending_comment_update(true);
        $.ajax({
            url: r.options.urls.update_build_comment,
            type: 'POST',
            dataType: 'JSON',
            data: {"build_id": self.id(), "comment": self.new_comment()},
            success: function (data) {
                self.pending_comment_update(false);
                self.editing_comment(false);
                self.build_comment(self.new_comment());
            },
            error: function () {
                self.pending_comment_update(false);
                self.editing_comment(false);
                self.comment_update_error(true);
            }
        });
    };

    return self;
}

function ReleasesMain(o) {
    /* {fetchUrl, deleteUrl} */
    var self = this;
    self.options = o;
    self.recipients = self.options.recipient_contacts;
    self.savedApps = ko.observableArray();
    self.doneFetching = ko.observable(false);
    self.buildState = ko.observable('');
    self.fetchState = ko.observable('');
    self.nextVersionToFetch = null;
    self.fetchLimit = 5;
    self.deployAnyway = {};
    self.currentAppVersion = ko.observable(self.options.currentAppVersion);
    self.lastAppVersion = ko.observable();
    self.buildButtonEnabled = ko.computed(function () {
        if (self.buildState() === 'pending' || self.fetchState() === 'pending') {
            return false;
        } else {
            return true;
        }
    });
    self.brokenBuilds = ko.computed(function () {
        var apps = self.savedApps();
        return _.some(apps, function (app) {
            return app.build_broken();
        });
    });
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
                savedApp = SavedApp(savedApps[i], self);
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
    self.reload_message = "Sorry, that didn't go through. " +
            "Please reload your page and try again";
    self.deleteSavedApp = function (savedApp) {
        savedApp._deleteState('pending');
        $.post(self.url('delete'), {saved_app: savedApp.id()}, function () {
            self.savedApps.remove(savedApp);
            savedApp._deleteState(false);
        }).error(function () {
            savedApp._deleteState('error');
            alert(self.reload_message);
        });
    };
    self.revertSavedApp = function (savedApp) {
        $.postGo(self.url('revertBuild'), {saved_app: savedApp.id()});
    };
    self.makeNewBuild = function () {
        if (self.buildState() === 'pending') {
            return false;
        }

        var url = self.url('currentVersion');
        self.fetchState('pending');
        $.get(
            self.url('currentVersion')
        ).success(function (data) {
            self.fetchState('');
            self.currentAppVersion(data.currentVersion);
            if (!data.latestRelease) {
                self.actuallyMakeBuild();
            } else if (data.latestRelease !== self.lastAppVersion()) {
                window.alert("The versions list has changed since you loaded the page.");
                self.reloadApps();
            } else if (self.lastAppVersion() !== self.currentAppVersion()) {
                self.actuallyMakeBuild();
            } else {
                window.alert("No new changes to deploy!");
            }
        }).error(function () {
            self.fetchState('error');
            window.alert(self.reload_message);
        });
    };
    self.reloadApps = function () {
        self.savedApps([]);
        self.nextVersionToFetch = null;
        self.getMoreSavedApps();
    };
    self.actuallyMakeBuild = function () {
        var comment = window.prompt(
            "Please write a comment about the build you're making " +
            "to help you remember later:"
        );
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
                var app = SavedApp(data.saved_app, self);
                self.addSavedApp(app, true);
            }
            self.buildState('');
        }).error(function () {
            self.buildState('error');
        });
    };
    // init
    setTimeout(function () {
        self.getMoreSavedApps();
    }, 0);
}
