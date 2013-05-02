var SelectFilteredMWGroup = function (users, selected_user, group_options) {
    var self = this,
        options = new Array();
    for (var i in group_options) {
        var group = group_options[i];
        options.push(new MobileWorker("group_"+group.group_id, group.name, true));
    }
    options = options.concat(users);
    self.mobile_workers = ko.observableArray(options);
    self.selected_mobile_worker = ko.observable(selected_user);
    self.grp_id = 'group_';
};

var MobileWorker = function (id, name, is_active) {
    this.val = id;
    this.text = name;
    this.is_active = is_active;
};

var GROUPID = 'group_';

ko.bindingHandlers.hiddenGroupFieldMW = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        if (value && value.indexOf(GROUPID) == 0) {
            $(element).attr('name', 'group');
            $(element).val(value.substring(GROUPID.length, value.length));
        } else {
            $(element).attr('name','');
        }
    }
};

ko.bindingHandlers.selectorMW = {
    update: function(element, valueAccessor) {
        var value = valueAccessor()();
        if (value && value.indexOf(GROUPID) == 0) {
            $(element).attr('name', 'filtered_individual');
        } else {
            $(element).attr('name','individual');
        }
    }
};