(function() {
    function HexParsr() {
        // private property
        var _paddingLeft = "sha256$" + Math.random().toString(36).slice(2, 8);
        var _paddingRight = Math.random().toString(36).slice(2, 8) + "=";

        b64EncodeUnicode = function(str){
          return encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, function(match, p1) {
                return String.fromCharCode('0x' + p1);
          });
        }

        this.addPadding = function(secret_password) {
            return _paddingLeft + secret_password + _paddingRight;
        }

        this.encode = function(password) {
            var secret_password = this.addPadding(window.btoa(b64EncodeUnicode(password)));
            return this.addPadding(window.btoa(secret_password));
        }
    }

    $(function(){
      var password_field=$("#id_auth-password");
      password_field.parents("form")[0].onsubmit = function(){
        password_encoder = new HexParsr();
        password_field.val(password_encoder.encode(password_field.val()));
      };
    });
})();