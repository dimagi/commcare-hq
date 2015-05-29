ko.bindingHandlers.select2 = {
    init: function(el, valueAccessor, allBindingsAccessor, viewModel) {
      ko.utils.domNodeDisposal.addDisposeCallback(el, function() {
        $(el).select2('destroy');
      });

      var allBindings = allBindingsAccessor(),
          select2 = ko.utils.unwrapObservable(allBindings.select2);

      $(el).select2(select2);
    },
    update: function (el, valueAccessor, allBindingsAccessor, viewModel) {
        var allBindings = allBindingsAccessor();

        if ("value" in allBindings) {
            if (allBindings.select2.multiple && allBindings.value().constructor != Array) {
                $(el).select2("val", allBindings.value().split(","));
            }
            else {
                $(el).select2("val", allBindings.value());
            }
        } else if ("selectedOptions" in allBindings) {
            var converted = [];
            var textAccessor = function(value) { return value; };
            if ("optionsText" in allBindings) {
                textAccessor = function(value) {
                    var valueAccessor = function (item) { return item; };
                    if ("optionsValue" in allBindings) {
                        valueAccessor = function (item) { return item[allBindings.optionsValue]; };
                    }
                    var items = $.grep(allBindings.options(), function (e) { return valueAccessor(e) == value;});
                    if (items.length === 0 || items.length > 1) {
                        return "UNKNOWN";
                    }
                    return items[0][allBindings.optionsText];
                };
            }
            $.each(allBindings.selectedOptions(), function (key, value) {
                converted.push({id: value, text: textAccessor(value)});
            });
            $(el).select2("data", converted);
        }
    }
};

function UsersViewModel(sms_users, location_id, submit_url) {
    var self = this;

    self.locationId = location_id;
    self.submitUrl = submit_url;

    self.users = ko.observableArray(sms_users);

    self.visibleUsers = ko.observableArray(ko.utils.arrayFilter(self.users(), function (user) {
        return !user.in_charge;
    }));

    self.inCharges = ko.observableArray(ko.utils.arrayFilter(self.users(), function (user) {
        return user.in_charge;
    }));

    var mapInChargesToIds = function() {
        return ko.utils.arrayMap(self.inCharges(), function (user) {
            return user.id;
        });
    };

    self.selectedUsers = ko.observableArray(mapInChargesToIds());

    self.save = function() {
        $('#in_charge_button').attr('disabled', true);
        $.ajax({
            type: 'POST',
            datatype: 'json',
            url: self.submitUrl,
            data: {
                users: self.selectedUsers(),
                location_id: self.locationId
            },
            success: function(response) {
                self.inCharges.removeAll();
                self.visibleUsers.removeAll();
                ko.utils.arrayForEach(self.users(), function(user) {
                   if (self.selectedUsers.indexOf(user.id) !== -1) {
                       user.in_charge = true;
                       self.inCharges.push(user);
                   } else {
                       user.in_charge = false;
                       self.visibleUsers.push(user);
                   }
                });

                $('#configureInCharge').modal('toggle');
                $('#in_charge_button').attr('disabled', false);
            }
        });
    };

    self.cancel = function() {
        self.selectedUsers.removeAll();
        ko.utils.arrayForEach(self.inCharges(), function(inCharge) {
            self.selectedUsers.push(inCharge.id);
        });
    };

}
