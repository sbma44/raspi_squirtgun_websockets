var inbox = new ReconnectingWebSocket("ws://"+ location.host + "/receive");
var outbox = new ReconnectingWebSocket("ws://"+ location.host + "/submit");

inbox.onmessage = function(message) {
  var data = JSON.parse(message.data);
};

inbox.onclose = function(){
    console.log('inbox closed');
    this.inbox = new WebSocket(inbox.url);

};

outbox.onclose = function(){
    console.log('outbox closed');
    this.outbox = new WebSocket(outbox.url);
};

function activate(){
  $('#system-status').removeClass('offline').addClass('online');
  $('#fire').removeClass('disabled');
}

function deactivate(){
  $('#system-status').removeClass('online').addClass('offline');
  $('#fire').addClass('disabled');
}

function checkStatus(){
  $.getJSON('/client-count', function(data){
    if (parseInt(data.client_count)>0){
      activate();
    }
    else{
      deactivate();
    }
  });
}

$(function(){
  window.FIRE_DURATION = 0.5;

  window.setInterval(checkStatus, 1000);

  $('#duration button').click(function(){
    $('#duration button').removeClass('active');
    $(this).addClass('active');
    window.FIRE_DURATION = $(this).attr('rel');
  });
});

$("#input-form").on("submit", function(event) {
  event.preventDefault();  
  outbox.send(JSON.stringify({ handle: 'FIRE', text: window.FIRE_DURATION, timestamp: Math.round(new Date().getTime() / 1000) }));
});
