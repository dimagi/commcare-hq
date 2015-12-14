var PasswordModel = function (weak, better, strong) {
    var self = this;
    self.weakMessage = weak;
    self.betterMessage = better;
    self.strongMessage = strong;
    self.password = ko.observable('');
    self.strength = ko.computed(function() {
        return zxcvbn(self.password()).score
    });
    self.color = ko.computed(function() {
        if (self.strength() < 2) {
            return "text-error text-danger";
        } else if (self.strength() == 2) {
            return "text-warning";
        } else {
            return "text-success";
        }
    });
    self.passwordHelp = ko.computed(function() {
        if (self.strength() < 2) {
            return self.weakMessage;
        } else if (self.strength() == 2) {
            return self.betterMessage;
        } else {
            return self.strongMessage;
        }
    });
};
