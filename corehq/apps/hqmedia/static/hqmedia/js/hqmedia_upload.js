/*
Requires jquery.form and jquery.progressbar
 */

function HQMediaUpload (args) {
    /* defaults...
        submit_url: '',
        progress_id_varname: 'X-Progress-ID',
        progress_checker_url: '',
        uploadbar: '#hqmedia_progressbar',
        processbar: null,
        progressbar_update_interval: 1000,
        upload_form_id: 'form#hqmedia_upload',
        upload_status_id: '#hqmedia_upload_status',
        static_url: '/static',
        form_error_class: '.error',
        submit_complete: function() {}
     */

    var _submit_url = (args.submit_url) ? args.submit_url : '',
        _progress_checker_url = (args.progress_checker_url) ? args.progress_checker_url : '',
        _progress_id_var = (args.progress_id_varname) ? args.progress_id_varname : 'X-Progress-ID',
        _upload_progressbar = (args.uploadbar) ? $(args.uploadbar) : $('#hqmedia_progressbar'),
        _process_progressbar = (args.processbar) ? $(args.processbar): null,
        _progress_bar_update_interval = (args.progressbar_update_interval) ? args.progressbar_update_interval : 1000,
        _upload_form_id = (args.upload_form_id) ? args.upload_form_id : 'form#hqmedia_upload',
        _submit_status_elem = (args.upload_status_id) ? $(args.upload_status_id) : $('#hqmedia_upload_status'),
        _static_url = (args.static_url) ? args.static_url : '/static',
        _error_class = (args.form_error_class) ? args.form_error_class: '.error';

    var _upload_form = $(_upload_form_id),
        _upload_form_errors = $(_upload_form_id+" "+_error_class),
        _upload_form_submit = $(_upload_form_id+" input[type='submit']");

    var _submit_completion_fn = (args.submit_complete) ? args.submit_complete : function () {};

    var submission_in_progress = false,
        poll_server_interval = 0;

    var progress_bar_options = {
            boxImage: _static_url+'hqmedia/img/progressbar.gif',
            barImage: {
                0:  _static_url+'hqmedia/img/progressbg_red.gif',
                30: _static_url+'hqmedia/img/progressbg_orange.gif',
                70: _static_url+'hqmedia/img/progressbg_green.gif'
            }
        };

    _upload_progressbar.progressBar(progress_bar_options);
    if(_process_progressbar)
        _process_progressbar.progressBar(progress_bar_options);

    function showRequest(formData, jqForm, options) {
        submission_in_progress = true;
        return true;
    }

    function showResponse(response) {
        if(response) {
            var error_list = $.parseJSON(response);
            cancelUpload();
            processErrors(error_list);
        }
    }

    function stopPollingServer(progressStatus) {
        _upload_progressbar.progressBar(progressStatus);
        if(_process_progressbar)
            _process_progressbar.progressBar(progressStatus);
        clearInterval(poll_server_interval);
        poll_server_interval = 0;
        submission_in_progress = false;
    }
    function cancelUpload() {
        stopPollingServer(0);
        _upload_form_submit.fadeIn();
        _submit_status_elem.fadeOut();
    }
    function processErrors(error_list) {
        for(var error in error_list) {
            var error_div = "#errors_"+error;
            $(error_div).text('');
            var messages = error_list[error];
            for(var i=0; i < messages.length; i++) {
                $(error_div).append(messages[i]);
            }
        }
    }
    function generateHQMediaUrl(url, progress_id){
        return url+"?"+_progress_id_var+"="+progress_id;
    }

    function startProgressBarUpdates(progress_id) {
        if(poll_server_interval != 0)
            clearInterval(poll_server_interval);
        if(submission_in_progress) {
            poll_server_interval = setInterval(function() {
                $.getJSON(generateHQMediaUrl(_progress_checker_url, progress_id), function (data) {
                    if (data == null) {
                        // uploading and processing has finished
                        stopPollingServer(100);
                        _upload_form_errors.text('');
                        _submit_status_elem.text('Finished.');
                        _submit_completion_fn();
                        return;
                    }
                    if(data.upload_aborted) {
                        cancelUpload();
                        if(data.error_list)
                            processErrors(data.error_list);
                        return;
                    }
                    _upload_form_errors.text('');

                    var upload_percentage = 100;
                    if(!data.upload_complete)
                        upload_percentage = Math.floor(100 * parseInt(data.uploaded) / parseInt(data.length));
                    _upload_progressbar.progressBar(upload_percentage);

                    if(_process_progressbar){
                        var processed_percentage = Math.floor(100 * parseInt(data.processed) / parseInt(data.processed_length));
                        _process_progressbar.progressBar(processed_percentage);
                    }
                });
            }, _progress_bar_update_interval);
        }
    }

    this.listenForUploads = function () {
        _submit_status_elem.fadeOut();
        _upload_form.submit(function(e) {
            var progress_id = $(this).children('.hqmedia_upload_id').val();
            if(progress_id) {
                var ajax_submit_options = {
                    dataType: 'multipart/form-data',
                    url: generateHQMediaUrl(_submit_url, progress_id),
                    beforeSubmit: showRequest,
                    success: showResponse,
                    type: 'post'
                };
                $(this).ajaxSubmit(ajax_submit_options);
                startProgressBarUpdates(progress_id);
            }else
                console.log("No upload id was provided!");
            _upload_form_submit.fadeOut();
            _submit_status_elem.text('Submitting...');
            _submit_status_elem.fadeIn();
            return false;
        });
    }
}

function guidGenerator() {
    // from http://stackoverflow.com/questions/105034/how-to-create-a-guid-uuid-in-javascript
    var S4 = function() {
       return (((1+Math.random())*0x10000)|0).toString(16).substring(1);
    };
    return (S4()+S4()+"-"+S4()+"-"+S4()+"-"+S4()+"-"+S4()+S4()+S4());
}