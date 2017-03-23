function HexParsr(salt1, salt2) {
    // private property
    var _paddingLeft = salt1;
    var _paddingRight = salt2;

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
