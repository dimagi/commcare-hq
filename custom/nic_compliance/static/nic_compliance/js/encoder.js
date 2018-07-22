hqDefine('nic_compliance/js/encoder', [
    'jquery',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    initialPageData
) {
    function HexParser() {
        var self = {};

        function paddingStr() {
            var s = Math.random().toString(36).slice(2, 8);
            return s.length === 6 ? s : paddingStr();
        }

        // private property
        var _paddingLeft = "sha256$" + paddingStr();
        var _paddingRight = paddingStr() + "=";

        var b64EncodeUnicode = function(str){
            return encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, function(match, p1) {
                return String.fromCharCode('0x' + p1);
            });
        };

        self.addPadding = function(secretPassword) {
            return _paddingLeft + secretPassword + _paddingRight;
        };

        self.encode = function(password) {
            if (password) {
                var secretPassword = self.addPadding(window.btoa(b64EncodeUnicode(password)));
                return self.addPadding(window.btoa(secretPassword));
            }
            return password;
        };

        return self;
    }

    $(function(){
        if (initialPageData.get("implement_password_obfuscation")) {
            var passwordField = $("#id_auth-password, #id_password");
            if (passwordField.length) {
                passwordField.parents("form")[0].onsubmit = function() {
                    var passwordEncoder = HexParser();
                    passwordField.val(passwordEncoder.encode(passwordField.val()));
                };
            }
            var resetPasswordFields = $("#id_old_password, #id_new_password1, #id_new_password2");
            if (resetPasswordFields.length) {
                $(resetPasswordFields[0]).parents("form")[0].onsubmit = function() {
                    for(var i=0; i < resetPasswordFields.length; i++) {
                        passwordField = $(resetPasswordFields[i]);
                        var passwordEncoder = HexParser();
                        passwordField.val(passwordEncoder.encode(passwordField.val()));
                    }
                };
            }
        }
    });

    return HexParser;
});
