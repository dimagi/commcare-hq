ko.bindingHandlers.clickable = (function () {
    function Clickable() {
        var self = this;
        self.init = function (element, valueAccessor, allBindingsAccessor, viewModel, bindingContext) {
            $(element).css({cursor: 'pointer'});
            return Clickable.prototype.init(element, valueAccessor, allBindingsAccessor, viewModel, bindingContext);
        }
    }
    Clickable.prototype = ko.bindingHandlers.click;
    return new Clickable();
}());

$(function () {
    var el = $('#fixtures-ui');
    function log (x) {
        console.log(x);
        return x;
    }
    function makeEditable(o) {
        o.saveState = ko.observable('saved');
        o.editing = ko.observable(false);
        o.startEditing = function () {
            o.editing(true);
            try {
                o._backup = o.serialize();
            } catch (e) {

            }
        };
        o.stopEdit = function () {
            o.editing(false);
        };
        o.cancelEdit = function () {
            o.editing(false);
            o.cancel();
        };
        o.saveEdit = function () {
            o.editing(false);
            o.save();
        };
        return o;
    }
    function makeDataType(o, app) {
        var self = ko.mapping.fromJS(o),
            raw_fields = self.fields();
        self.fields = ko.observableArray([]);
        self.data_items = ko.observableArray([]);
        makeEditable(self);
        if (!o._id) {
            self._id = ko.observable();
        }
        self.aboutToDelete = ko.observable(false);
        self.addField = function (data, event, o) {
            var i, field;
            if (o) {
                field = {
                    tag: ko.observable(o.tag),
                    editing: ko.observable(false)
                };
            } else {
                field = {
                    tag: ko.observable(""),
                    editing: ko.observable(true)
                };
            }
            field.editTag = ko.computed({
                read: function () {
                    return field.tag();
                },
                write: function (tag) {
                    var j, noRepeats = true;
                    for (j = 0; j < self.fields().length; j += 1) {
                        if (self.fields()[j].tag === tag) {
                            noRepeats = false;
                        }
                    }
                    if (noRepeats) {
                        var oldTag = field.tag;
                        field.tag(tag);
                    }
                    // all the items have a pointer to this field, so the tag name changes automatically
                    // but they still need to be saved
                    for (j = 0; j < self.data_items().length; j += 1) {
                        self.data_items()[i].save();
                    }
                }
            });
            self.fields.push(field);
            for (i = 0; i < self.data_items().length; i += 1) {
                self.data_items()[i].fields.push({value: ko.observable(""), tag: field.tag});
            }
        };
        self.removeField = function (field) {
            var i,
                index = self.fields.indexOf(field),
                itemFields;
            self.fields.remove(field);
            for (i = 0; i < self.data_items().length; i += 1) {
                itemFields = self.data_items()[i].fields;
                itemFields.remove(itemFields()[index]);
            }
        };
        for (var i = 0; i < raw_fields.length; i += 1) {
            self.addField(undefined, undefined, {tag: raw_fields[i]});
        }
        self.addDataItem = function (data, event) {
            var item = makeDataItem({
                _id: null,
                fields: {}
            });
            item.startEditing();
            self.data_items.push(item);
        };
        self.removeDataItem = function (item, event) {
            self.data_items.destroy(item);
            item.save();
        };
        function makeDataItem(o) {
            var item = ko.mapping.fromJS(o);
            var fields_dict = item.fields;
            item.users = item.users || ko.observableArray();
            item.groups = item.groups || ko.observableArray();
            item.fields = ko.observableArray([]);
            for (var i = 0; i < self.fields().length; i += 1) {
                item.fields.push({
                    value: fields_dict[self.fields()[i].tag()] || ko.observable(""),
                    tag: self.fields()[i].tag
                });
            }
            makeEditable(item);
            item.groupsAndUsers = makeEditable({});

            function remainingOwners(myList, globalList) {
                var remaining = [],
                    i,
                    owner_ids = {};
                for (i = 0; i < myList.length; i += 1) {
                    if (!myList[i]._destroy) {
                        owner_ids[myList[i]._id()] = true;
                    }
                }

                for (i = 0; i < globalList.length; i += 1) {
                    if (!owner_ids[globalList[i]._id]) {
                        remaining.push(globalList[i]);
                    }
                }
                return remaining;
            }

            function addOwner(owners, owner, save) {
                owner = ko.mapping.fromJS(owner);
                owner._waiting = ko.observable(true);
                owners.push(owner);
                save(owner);
            }

            function removeOwner(owners, owner, save) {
                owner._waiting = ko.observable(true);
                owners.destroy(owner);
                save(owner);
            }

            function saveOwner(type, owner) {
                $.ajax({
                    type: owner._destroy ? 'delete' : 'post',
                    url: 'data-items/' + self._id() + '/' + item._id() + '/' + type + '/' + owner._id(),
                    success: function () {
                        owner._waiting(false);
                    }
                });
            }

            item.remainingGroups = ko.computed(function () {
                return remainingOwners(item.groups(), app.groups);
            });
            item.addGroup = function (o) {
                return addOwner(item.groups, o, item.saveGroup);
            };
            item.removeGroup = function (o) {
                return removeOwner(item.groups, o, item.saveGroup);
            };
            item.saveGroup = function (o) {
                return saveOwner('groups', o);
            };

            item.remainingUsers = ko.computed(function () {
                return remainingOwners(item.users(), app.users);
            });
            item.addUser = function (o) {
                return addOwner(item.users, o, item.saveUser);
            };
            item.removeUser = function (o) {
                return removeOwner(item.users, o, item.saveUser);
            };
            item.saveUser = function (o) {
                return saveOwner('users', o);
            };

            item.serialize = function () {
                return {
                    fields: (function () {
                        var i, fields = {};
                        for (i = 0; i < item.fields().length; i += 1) {
                            fields[item.fields()[i].tag()] = item.fields()[i].value();
                        }
                        return fields;
                    }())
                };
            };
            item.save = function () {
                $.ajax({
                    type: item._id() ? (item._destroy ? 'delete': 'put') : 'post',
                    url: 'data-items/' + self._id() + '/' + (item._id() || ''),
                    data: JSON.stringify(item.serialize()),
                    dataType: 'json',
                    success: function (data) {
                        item.saveState('saved');
                        if (!item._id()) {
                            item._id(data._id);
                        }
                    }
                });
                item.saveState('saving');
            };
            item.cancel = function () {
                var backup = item._backup,
                    i,
                    tag;
                for (i = 0; i < item.fields().length; i += 1) {
                    tag = item.fields()[i].tag();
                    item.fields()[i].value(backup.fields[tag]);
                }
            };
            return item;
        }

        if (self._id) {
            $.ajax({
                url: 'data-items/' + self._id() + '/?groups=true&users=true',
                type: 'get',
                dataType: 'json',
                success: function (data) {
                    for (var i = 0; i < data.length; i += 1) {
                        self.data_items.push(makeDataItem(data[i]));
                    }
                }
            });
        }
        self.save = function () {
            $.ajax({
                type: self._id() ? (self._destroy ? 'delete' : 'put') : 'post',
                url: 'data-types/' + (self._id() || ''),
                data: JSON.stringify(self.serialize()),
                dataType: 'json',
                success: function (data) {
                    self.saveState('saved');
                    if (!self._id()) {
                        self._id(data._id)
                    }
                }
            });
            self.saveState('saving');
        };
        self.serialize = function () {
            return log({
                _id: self._id(),
                name: self.name(),
                tag: self.tag(),
                fields: (function () {
                    var fields = [], i;
                    for (i = 0; i < self.fields().length; i += 1) {
                        fields.push(self.fields()[i].tag());
                    }
                    return fields;
                }())
            });
        };
        return self;
    }
    function App() {
        var self = this;
        self.data_types = ko.observableArray([]);
        self.loading = ko.observable(0);

        self.addDataType = function () {
            var dataType = makeDataType({
                name: "",
                tag: "",
                fields: ko.observableArray([])
            }, self);
            dataType.editing(true);
            self.data_types.push(dataType);
        };
        self.removeDataType = function (dataType) {
            self.data_types.destroy(dataType);
            dataType.save();
        };
        self.loadData = function () {
            self.loading(self.loading() + 3);
            $.ajax({
                url: 'data-types/',
                type: 'get',
                dataType: 'json',
                success: function (data) {
                    var dataType;
                    for (var i = 0; i < data.length; i += 1) {
                        self.data_types.push(makeDataType(data[i], self));
                        dataType = self.data_types()[i];
                    }
                    self.loading(self.loading() - 1)
                }
            });
            $.ajax({
                url: 'groups/',
                type: 'get',
                dataType: 'json',
                success: function (data) {
                    self.groups = data;
                    self.loading(self.loading() - 1)
                }
            });
            $.ajax({
                url: 'users/',
                type: 'get',
                dataType: 'json',
                success: function (data) {
                    self.users = data;
                    self.loading(self.loading() - 1)
                }
            });
        };
    }
    var app = new App();
    ko.applyBindings(app, el.get(0));
    el.show();
    app.loadData();
});