It can get a little annoying keeping track of what machines are called (`hqpillowtop0`... or is it `hqpillowtop1` now?). Well, now you don't have to keep track, you can just run

```
scripts/inventory/ssh production pillowtop
```

and it'll (1) tell you and (2) ssh into that machine

```
$ scripts/inventory/ssh production pillowtop
ssh hqpillowtop0.internal.commcarehq.org
Welcome to Ubuntu 12.04.5 LTS (GNU/Linux 3.2.0-75-generic x86_64)

 * Documentation:  https://help.ubuntu.com/
New release '14.04.1 LTS' available.
Run 'do-release-upgrade' to upgrade to it.

Last login: Wed May  4 20:50:24 2016 from 192.168.237.194
droberts@hqpillowtop0:~$
```

If that doesn't uniquely identify a machine, it'll tell you what to do

```
$ scripts/inventory/ssh production webworkers
There are 3 production webworkers machines:

hqdjango12.internal.commcarehq.org
hqdjango13.internal.commcarehq.org
hqdjango14.internal.commcarehq.org

Use `scripts/inventory/ssh production webworkers 1` to get the first
```

And then you can run `scripts/inventory/ssh production webworkers 1` to get the first (or `2` for the second, etc.).

All commands work with `scripts/inventory/mosh` instead as well.
