'use strict';
hqDefine("cloudcare/js/config", [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/main',
], function (
    $,
    _,
    ko,
    initialPageData,
    hqMain
) {
    $(function () {
        var makeDB = function (list) {
            /* turn a list into a dict indexed by each object's _id */
            var db = {};
            list.sort(function (a, b) {return a.name > b.name;});
            for (var i = 0; i < list.length; i++) {
                var obj = list[i];
                db[obj._id] = obj;
            }
            db._sorted = list;
            return db;
        };
        var access = initialPageData.get('access');
        var appDB = makeDB(initialPageData.get('apps'));
        var groupDB = makeDB(initialPageData.get('groups'));

        var addJsonAccess = function (o) {
            o.JSON = ko.computed({
                read: function () {
                    return JSON.stringify(o());
                },
                write: function (value) {
                    o(JSON.parse(value));
                },
            });
            return o;
        };

        var ApplicationAccess = function () {
            var self = this;
            self.restrict = addJsonAccess(ko.observable());
            self.app_groups = ko.observableArray();
            self._lock = ko.observable(false);
        };
        ApplicationAccess.wrap = function (o) {
            var self = new ApplicationAccess();
            self.restrict(o.restrict);
            for (var i = 0; i < o.app_groups.length; i++) {
                self.app_groups.push(AppGroup.wrap(o.app_groups[i]));
            }
            self._id = o._id;
            self._rev = o._rev;
            return self;
        };

        var AppGroup = function () {
            var self = this;
            self.group_id = linkToDB(groupDB, ko.observable());
            self.app_id = linkToDB(appDB, ko.observable());
        };
        AppGroup.wrap = function (o) {
            var self = new AppGroup();
            self.group_id(o.group_id);
            self.app_id(o.app_id);
            return self;
        };

        var linkToDB = function (db, o) {
            o.obj = function () {
                return db[o()];
            };
            return o;
        };

        var $home = $('#cloudcare-app-settings');
        var Controller = function (options) {
            var self = this;
            self.groupDB = options.groupDB;
            self.appDB = options.appDB;
            self.applicationAccess = ApplicationAccess.wrap(options.access);
            self.saveButton = hqMain.initSaveButton({
                save: function () {
                    self.saveButton.ajax({
                        url: initialPageData.reverse("cloudcare_app_settings"),
                        type: 'put',
                        dataType: 'json',
                        data: ko.mapping.toJSON(self.applicationAccess),
                        success: function (data) {
                            self.applicationAccess._rev = data._rev;
                        },
                    });
                },
            });
            self.appsByGroup = ko.computed(function () {
                var lookup = {};
                var returnValue = [];
                for (var i = 0; i < self.applicationAccess.app_groups().length; i++) {
                    var group = self.applicationAccess.app_groups()[i];
                    if (!_.has(lookup, group.group_id())) {
                        lookup[group.group_id()] = {
                            group: group.group_id.obj(),
                            apps: [],
                        };
                    }
                    lookup[group.group_id()].apps.push(group.app_id.obj());
                }
                for (var id in lookup) {
                    if (_.has(lookup, id)) {
                        returnValue.push(lookup[id]);
                    }
                }
                return returnValue;
            });
        };
        var controller = new Controller({
            access: access,
            groupDB: groupDB,
            appDB: appDB,
        });
        $home.koApplyBindings(controller);
        $home.show();
        $(document).on('change', '#cloudcare-app-settings *', function () {
            controller.saveButton.fire('change');
        });
    });
});
