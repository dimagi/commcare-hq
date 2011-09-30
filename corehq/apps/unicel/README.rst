================
A django application for integrating with the UNICEL SMS gateway 
================

PUSH SMS URL (to send outgoing sms): 

http://www.unicel.in/SendSMS/sendmsg.php?uname=[account]&pass=[password]&send=Promo&dest=[destination]&msg=[content]

Inbound SMS URL
http://yourdomain.com/unicel/in/&send=[sender]&dest=[destination]&msg=[content]&stime=[m/d/y h:m:s AM/PM]