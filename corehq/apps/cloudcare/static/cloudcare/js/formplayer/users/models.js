'use strict';
hqDefine("cloudcare/js/formplayer/users/models", [
    "underscore",
    "backbone",
    "analytix/js/kissmetrix",
    "cloudcare/js/formplayer/constants",
], function (
    _,
    Backbone,
    kissmetrics,
    Const
) {
    var self = {};

    self.User = Backbone.Model.extend();
    self.CurrentUser = Backbone.Model.extend({
        initialize: function () {
            this.on('change:versionInfo', function (model) {
                if (model.previous('versionInfo') && model.get('versionInfo')) {
                    this.trackVersionChange(model);
                }
            }.bind(this));
        },

        isMobileWorker: function () {
            return this.username.endsWith('commcarehq.org');
        },

        getDisplayUsername: function () {
            if (this.isMobileWorker()) {
                return this.username.split('@')[0];
            }
            return this.username;
        },

        trackVersionChange: function (model) {
            kissmetrics.track.event(
                '[app-preview] App version changed',
                {
                    previousVersion: model.previous('versionInfo'),
                    currentVersion: model.get('versionInfo'),
                }
            );
        },
    });

    self.saveDisplayOptions = function (displayOptions) {
        var displayOptionsKey = self.getDisplayOptionsKey();
        localStorage.setItem(displayOptionsKey, JSON.stringify(displayOptions));
    };

    self.getSavedDisplayOptions = function () {
        var displayOptionsKey = self.getDisplayOptionsKey();
        try {
            return JSON.parse(localStorage.getItem(displayOptionsKey));
        } catch (e) {
            window.console.warn('Unable to parse saved display options');
            return {};
        }
    };

    self.getDisplayOptionsKey = function () {
        var user = self.getCurrentUser();
        return [
            user.environment,
            user.domain,
            user.username,
            'displayOptions',
        ].join(':');
    };

    var userInstance;
    self.getCurrentUser = function () {
        if (!userInstance) {
            userInstance = new self.CurrentUser();
        }
        return userInstance;
    };

    self.setCurrentUser = function (options) {
        self.getCurrentUser();       // ensure userInstance is populated

        userInstance.username = options.username;
        userInstance.domain = options.domain;
        userInstance.formplayer_url = options.formplayer_url;
        userInstance.debuggerEnabled = options.debuggerEnabled;
        userInstance.environment = options.environment;
        userInstance.changeFormLanguage = options.changeFormLanguage;

        var savedDisplayOptions = _.pick(
            self.getSavedDisplayOptions(),
            Const.ALLOWED_SAVED_OPTIONS
        );
        userInstance.displayOptions = _.defaults(savedDisplayOptions, {
            singleAppMode: options.singleAppMode,
            landingPageAppMode: options.landingPageAppMode,
            phoneMode: options.phoneMode,
            oneQuestionPerScreen: options.oneQuestionPerScreen,
            language: options.language,
        });

        return userInstance;
    };

    return self;
});
