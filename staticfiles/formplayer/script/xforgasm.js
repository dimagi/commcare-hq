

function WebFormSession(params) {
  if (params.form_uid) {
    this.form_spec = {type: 'uid', val: params.form_uid};
  } else if (params.form_content) {
    this.form_spec = {type: 'raw', val: params.form_content};
  } else if (params.form_url) {
    this.form_spec = {type: 'url', val: params.form_url};
  } 

  //todo: support instance_xml ?
  this.session_data = params.session_data;

  this.onsubmit = params.onsubmit;
  this.onpresubmit = params.onpresubmit || function(){ return true; };
  this.onlanginfo = params.onlanginfo || function(f, langs){};
  this.onerror = params.onerror || function(resp){};

  this.urls = {
    xform: params.xform_url,
    autocomplete: params.autocomplete_url,
  };

  this.load = function($div, $loading, init_lang) {
    this.$div = $div;
    this.$loading = $loading || $div.find('#loading');

    this.$div.addClass('webforms');

    var sess = this;
    var adapter = new xformAjaxAdapter(this.form_spec, this.session_data, null,
                                       function(p, cb, bl) { sess.serverRequest(p, cb, bl); },
                                       function(p) { sess.submit(p); },
                                       this.onpresubmit
                                       );
    adapter.loadForm($div, init_lang, this.onlanginfo, this.onerror);
  }

  this.submit = function(params) {
    this.inputActivate(false);
    this.inputActivate = function(){}; //hack to keep input fields disabled during final POST

    this.onsubmit(params.output);
  }

  this.serverRequest = function(params, callback, blocking) {
    var url = this.urls.xform;
    this._serverRequest(
      function (cb) {
        jQuery.ajax(
            {type: "POST",
             url: url, 
             data: JSON.stringify(params), 
             success: cb, 
             dataType: "json",
             error: function (jqXHR, textStatus, errorThrown) { 
                console.log("Got an unexpected server error!", textStatus, errorThrown);
             }
        });
        
      },
      callback,
      blocking
    );
  }

  this.BLOCKING_REQUEST_IN_PROGRESS = false;
  this.LAST_REQUEST_HANDLED = -1;
  this.NUM_PENDING_REQUESTS = 0;
  // makeRequest - function that takes in a callback function and executes an
  //     asynchronous request (GET, POST, etc.) with the given callback
  // callback - callback function for request
  // blocking - if true, no further simultaneous requests are allowed until
  //     this request completes
  this._serverRequest = function(makeRequest, callback, blocking) {
    if (this.BLOCKING_REQUEST_IN_PROGRESS) {
      return;
    }

    this.NUM_PENDING_REQUESTS++;
    this.$loading.show();

    if (blocking) {
      this.inputActivate(false); // sets BLOCKING_REQUEST_IN_PROGRESS
    }
    var sess = this;
    makeRequest(function (resp) {
        // ignore responses older than the most-recently handled
        if (resp.seq_id && resp.seq_id < sess.LAST_REQUEST_HANDLED) {
          return;
        }
        sess.LAST_REQUEST_HANDLED = resp.seq_id;

        callback(resp);
        if (blocking) {
          sess.inputActivate(true); // clears BLOCKING_REQUEST_IN_PROGRESS
        }

        sess.NUM_PENDING_REQUESTS--;
        if (sess.NUM_PENDING_REQUESTS == 0) {
          sess.$loading.hide();
        }
      });
  }

  this.inputActivate = function(enable) {
    this.BLOCKING_REQUEST_IN_PROGRESS = !enable;
    this.$div.find('input').attr('disabled', enable ? null : 'true');
    this.$div.find('a').css('color', enable ? 'blue' : 'grey');
  }

}

function submit_form_post(xml) {
  submit_redirect({type: 'form-complete', output: xml});
}