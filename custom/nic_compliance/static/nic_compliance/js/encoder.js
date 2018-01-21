hqDefine('nic_compliance/js/encoder', function () {
    function HexParsr() {
        function randomStr() {
            var s = Math.random().toString(36).slice(2, 8);
            return s.length === 6 ? s : randomStr();
        }

        // private property
        var _salt = randomStr();
        var _paddingLeft = "sha256$" + _salt;
        var _paddingRight = randomStr() + "=";

        var b64EncodeUnicode = function(str){
            return encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, function(match, p1) {
                return String.fromCharCode('0x' + p1);
            });
        };

        this.addPadding = function(secret_password) {
            return _paddingLeft + secret_password + _paddingRight;
        };

        this.obfuscate = function(password) {
            var secret_password = this.addPadding(window.btoa(b64EncodeUnicode(password)));
            return this.addPadding(window.btoa(secret_password));
        };

        this.encode = function(password) {
            if(password) {
                var shaObj256 = new jsSHA256("SHA-256", "TEXT");
                shaObj256.update(password);
                var sha256_hashed = shaObj256.getHash("HEX");

                var shaObj256 = new jsSHA256("SHA-256", "TEXT");
                shaObj256.update(_salt); // prepend salt to hashed password
                shaObj256.update(sha256_hashed);
                var hashed_password = "sha256hash$" + _salt + "$" + shaObj256.getHash("HEX");
                return this.obfuscate(hashed_password);
            }
            return password;
        };
    }

    $(function(){
        // login page
        var login_password_field = $("#email-auth-password");
        if(login_password_field.length) {
            login_password_field.parents("form")[0].onsubmit = function() {
                var password_encoder = new HexParsr();
                login_password_field.val(password_encoder.encode(login_password_field.val()));
            };
        }

        // sign up page
        var signup_password_field = $("#register-webuser-password");
        if (signup_password_field.length) {
            signup_password_field.parents("form")[0].onsubmit = function() {
                var password_encoder = new HexParsr();
                signup_password_field.val(password_encoder.obfuscate(signup_password_field.val()));
            };
        }

        // for web user forgot password and reset password
        var password_reset_fields = $("#id_old_password, #id_new_password1, #id_new_password2");
        if(password_reset_fields.length) {
            var password_reset_form = $(password_reset_fields[0]).parents('form')[0];
            if(password_reset_form) {
                password_reset_form.onsubmit = function() {
                    var password_encoder = new HexParsr();
                    var old_password_field = $("#id_old_password");
                    if(old_password_field) {
                        old_password_field.val(password_encoder.encode(old_password_field.val()));
                    }

                    var new_password_fields = $("#id_new_password1, #id_new_password2");
                    for(var i=0; i<new_password_fields.length; i++) {
                        var password_field = $(new_password_fields[i]);
                        password_field.val(password_encoder.obfuscate(password_field.val()));
                    }
                };
            }
        }
    });

    return HexParsr;
});
