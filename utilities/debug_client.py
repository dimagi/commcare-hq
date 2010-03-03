#!/usr/bin/env python

#
# Code taken mostly from the python std lib docs, section 21.17
#


import socket
import sys

def console_msg( *args ):
    
    sargs = [str(x) for x in args]
    data = ' '.join(sargs)
    
    # Common failure is that the server isn't running. Don't die if so.
    try:
        HOST, PORT = "localhost", 9999
        
        # Create a socket (SOCK_STREAM means a TCP socket)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Connect to server and send data
        sock.connect((HOST, PORT))
        sock.send(str(data) + "\n")
        
        # Receive data from the server and shut down
        received = sock.recv(1024)
        sock.close()
    except:
        pass

if __name__ == '__main__':
    data = " ".join(sys.argv[1:])
    console_msg(data)
