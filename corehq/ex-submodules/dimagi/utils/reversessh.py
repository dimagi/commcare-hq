import os

# this is a script that allows you to log in to remote servers that
# are not easily accessible via the internet, due to aggressive
# NATing, intermittent connections, dynamic IPs, and such.

# this script runs on the remote server, called frequently via cron-
# job. when called, it attempts to open up an ssh tunnel to a
# central server, and forwards a port on the central server back to
# the ssh port on the remote server. this allows you to ssh into the
# remote server, bypassing all firewalls, etc., provided it has
# enough connectivity to keep the tunnel open

# if the tunnel is up, then on the central server, you'd run:
#
#   ssh {remoteuser}@localhost -p {PORT}
#
# and you'd log in as 'remoteuser' on the remote server

# when called via cron job, the script is robust against dropped
# connections, stale connections, etc. if the remote server has
# connectivity, you SHOULD be able to remote in

# the recommended cron interval is 3-5 minutes

# you must configure the remote server such that it can log into
# the central server automatically via an ssh key, as no one will
# be there to type in a password.
# see: http://oreilly.com/pub/h/66 for setting that up

# server that is easily reachable on the internet
SERVER = 'central-server.example' 

# user account that the remote server can use to log into the central
# server. this should probably be a custom account not used for anything
# else, with limited permissions. multiple remote computers can share
# this account
USER = 'remoteserver' 

# the (unprivileged) port that will be the incoming end of the ssh
# tunnel. this must be unique per remote computer
PORT = 7356

ssh_cmd = 'ssh %s@%s -N -R %d:localhost:22 -C -o "BatchMode yes" -o "ExitOnForwardFailure yes" -o "ServerAliveInterval 60"' % (USER, SERVER, PORT)
os.popen(ssh_cmd)

# BatchMode causes the command to terminate if any user intervention
# is required (such as if a password prompt was going to be shown)

# ExitOnForwardFailure causes the command to terminate if an active
# tunnel is already open (because the desired forwarding port will
# already be in use). this is how we can safely keep calling the
# script in a cron loop w/o opening many redundant sessions

# ServerAliveInterval causes the open session to terminate if the
# connection drops and it doesn't get any pingbacks from the central
# server after a short period of time. this prevents the session from
# going stale (not connected but still sitting on the port) which
# would thwart any reconnection attempts

# you probably also want to set the ClientAliveInterval setting of
# the ssh daemon on the central server to do the same thing on the
# other end. otherwise you might have open ports on the central
# server making it appear you have open tunnels to your remote
# servers, but they have in fact gone stale. you would have to
# forcibly terminate those sessions, then wait for the remote server
# to reconnect, if it can.

# a tool like nmap or lsof can list open ports, and you can see which
# remote servers currently have open tunnels

# pro-tip, when ssh'ing over an unreliable connection, always open
# a 'screen' session as your first act, then do everything else inside
# that session. then, if you get disconnected, your session and any
# active jobs won't be forcibly terminated, and you can resume the
# session when you reconnect
