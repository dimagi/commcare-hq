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
      var password_field = $("#id_auth-password");
      if(password_field.length) {
          password_field.parents("form")[0].onsubmit = function() {
            password_encoder = new HexParsr();
            password_field.val(password_encoder.encode(password_field.val()));
          };
      }
      var reset_password_fields = $("#id_old_password, #id_new_password1, #id_new_password2");
      if(reset_password_fields.length) {
          $(reset_password_fields[0]).parents("form")[0].onsubmit = function() {
              for(var i=0; i<reset_password_fields.length; i++) {
                  password_field = $(reset_password_fields[i]);
                  password_encoder = new HexParsr();
                  password_field.val(password_encoder.encode(password_field.val()));
              }
          }
      }
    });
})();