hqDefine('nic_compliance/js/encoder', function () {
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
            if(password) {
                var secretPassword = self.addPadding(window.btoa(b64EncodeUnicode(password)));
                return self.addPadding(window.btoa(secretPassword));
            }
            return password;
        };

        return self;
    }

    $(function(){
        if (hqImport("hqwebapp/js/initial_page_data").get("implement_password_obfuscation")) {
            var ids = _.filter([
                'id_auth-password',
                'id_password',
                'id_old_password',
                'id_new_password1',
                'id_new_password2',
            ], function (id) {
                return $('#' + id).length;
            });
            _.each(ids, function (id) {
                var $field = $('#' + id),
                    $form = $field.closest("form"),
                    fieldType,
                    unencodedValue;
                $form.submit(function () {
                    var passwordEncoder = HexParser();
                    unencodedValue = $field.val();
                    fieldType = $field.attr("type");
                    $field.attr("type", "password");
                    $field.val(passwordEncoder.encode(unencodedValue));
                });
                $(document).on("ajaxComplete", function (e, xhr, options) {
                    if ($form.attr("action").endsWith(options.url)) {
                        $field.attr("type", fieldType);
                        $field.val(unencodedValue);
                    }
                });
            });
        }
    });

    return HexParser;
});
