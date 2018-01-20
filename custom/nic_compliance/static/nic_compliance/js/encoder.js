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

        this.encode = function(password) {
            if(password) {
                var shaObj256 = new jsSHA256("SHA-256", "TEXT");
                shaObj256.update(password)
                var sha256_hashed = shaObj256.getHash("HEX");

                var shaObj256 = new jsSHA256("SHA-256", "TEXT");
                shaObj256.update(_salt) // prepend salt to hashed password
                shaObj256.update(sha256_hashed)
                var hashed_password = "sha256hash$" + _salt + "$" + shaObj256.getHash("HEX");
                var secret_password = this.addPadding(window.btoa(b64EncodeUnicode(hashed_password)));
                var final_password = this.addPadding(window.btoa(secret_password));
                return final_password;
            }
            return password;
        };
    }

    $(function(){
        var password_field = $("#id_auth-password, #id_password");
        if(password_field.length) {

            password_field.parents("form")[0].onsubmit = function() {
                var password_encoder = new HexParsr();
                password_field.val(password_encoder.encode(password_field.val()));
            };
        }
        var reset_password_fields = $("#id_old_password, #id_new_password1, #id_new_password2");
        if(reset_password_fields.length) {
            $(reset_password_fields[0]).parents("form")[0].onsubmit = function() {
                for(var i=0; i<reset_password_fields.length; i++) {
                    password_field = $(reset_password_fields[i]);
                    var password_encoder = new HexParsr();
                    password_field.val(password_encoder.encode(password_field.val()));
                }
            };
        }
    });

    return HexParsr;
});
