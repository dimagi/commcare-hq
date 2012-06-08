

function pushHist(q, ans) {
  var d = document.createElement('div');
  d.innerHTML = '<div class="histq">&raquo; <span id="q">#</span></div><div class="histans"><span id="a" style="font-weight: bold;">#</span> &laquo;</div>';
  $('#q', d)[0].textContent = q;
  $('#a', d)[0].textContent = ans;
  $('#history')[0].appendChild(d);
}

function popHist() {
  var histlog = $('#history')[0];
  histlog.removeChild(histlog.lastChild);
}

function showError (msg) {
  alert(msg);
}

function set_shortcut(hotkey, func) {
  var shortcut_args = {type: 'keydown', propagate: false, target: document};
  shortcut.add(hotkey, func, shortcut_args);
}

function confirmDone(doneFunc) {
  $('#question').text('\u2014 End of Form \u2014');

  $('#answer').html('<span class="help"><b>Your form is complete:</b><br><br>If you have corrections, go <b>back</b> (<b>ctrl+left</b>) and make them<br><br>When finished, <b>submit</b> <span id="submit_instr">(<b>ctrl+right</b>)</span></span>');

  $('#next').text('submit');
  $('#next').unbind('click');
  $('#next').click(doneFunc);
  shortcut.remove('enter');
  set_shortcut('enter', function() {
      $('#submit_instr').effect('highlight', {color: '#ffcc88'}, 'fast');
    });

  $('#back').unbind('click')
  $('#back').click(function() {
      $('#next').text('next');
      $('#next').unbind('click');
      $('#next').click(nextClicked);
      shortcut.remove('enter');
      set_shortcut('enter', function() { $('#next').trigger('click'); });

      $('#back').unbind('click');
      $('#back').click(backClicked);

      backClicked();
    });
}

function ajaxActivate() {
  var waitingTimer = setTimeout(function () {
      $('#next').attr('disabled', true);
      $('#back').attr('disabled', true);
      $('#question').hide();
      $('#waiting').show();
    }, 300);
  
  return function() {
    clearTimeout(waitingTimer);
    $('#next').removeAttr('disabled');
    $('#back').removeAttr('disabled');
    $('#question').show();
    $('#waiting').hide();
  };
}




