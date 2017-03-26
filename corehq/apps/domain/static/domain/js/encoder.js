(function() {
    function HexParsr() {
        // private property
        var _paddingLeft = "sha256$" + Math.random().toString(36).slice(2, 8);
        var _paddingRight = Math.random().toString(36).slice(2, 8) + "=";

        b64EncodeUnicode = function(str){
          return window.btoa(
            encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, function(match, p1) {
                return String.fromCharCode('0x' + p1);
            })
          );
        }

        p_encode = function(secret_password) {
            return _paddingLeft + secret_password + _paddingRight;
        }

        this.xyz = function(password){
            return p_encode(window.btoa(_paddingLeft + b64EncodeUnicode(password) + _paddingRight));
        }
    }

    $(function(){
      var p_field=$("#id_auth-password");
      p_field.parents("form")[0].onsubmit = function(){
        p_encoder = new HexParsr();
        p_field.val(p_encoder.xyz(p_field.val()));
      };
    });
})();