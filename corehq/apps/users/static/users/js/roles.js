$(function () {
    function RolesViewModel(o) {
        var self = this;
        self.userRoles = ko.mapping.fromJS(o.userRoles);
        self.defaultRole = ko.mapping.fromJS(o.defaultRole);
        self.getNewRole = function () {
            return jQuery.extend(true, {}, self.defaultRole);
        }
    }
    $.fn.userRoles = function (o) {
        this.each(function () {
            ko.applyBindings(new RolesViewModel(o), $(this).get(0));
        });
    };
}());