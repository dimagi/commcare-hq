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

function User(user) {
    this.id = user.id;
    this.full_name = user.full_name;
    this.phone_numbers = user.phone_numbers;
    this.in_charge = ko.observable(user.in_charge);
    this.url = user.url;
    this.locationName = user.location_name;

    this.optionsText = this.full_name + " (" + this.locationName + ")";
}

function UsersViewModel(sms_users, district_in_charges, location_id, submit_url) {
    var self = this;
    self.locationId = location_id;
    self.submitUrl = submit_url;

    self.users = ko.observableArray(sms_users.map(function(user) { return new User(user);}));

    self.districtInCharges = ko.observableArray(district_in_charges.map(function(user) { return new User(user);}));

    self.inCharges = ko.computed(function() {
        return ko.utils.arrayFilter(self.districtInCharges(), function (user) {
            return user.in_charge();
        });
    }, this);

    var mapInChargesToIds = function() {
        return ko.utils.arrayMap(self.inCharges(), function (user) {
            return user.id;
        });
    };

    self.selectedUsers = ko.observableArray(mapInChargesToIds());

    self.visibleUsers = function() {
        return ko.utils.arrayFilter(self.users(), function(user) {
            return mapInChargesToIds().indexOf(user.id) === -1;
        });
    };

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
                ko.utils.arrayForEach(self.districtInCharges(), function(user) {
                   user.in_charge(self.selectedUsers.indexOf(user.id) !== -1);
                });

                ko.utils.arrayForEach(self.users(), function(user) {
                   user.in_charge(self.selectedUsers.indexOf(user.id) !== -1);
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
