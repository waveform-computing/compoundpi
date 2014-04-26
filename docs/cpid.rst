.. _cpid:

====
cpid
====

This is the server daemon for the Compound Pi application. Starting the
application with no arguments starts the server in the foreground. The server
can be configured through command line arguments or a configuration file (which
defaults to ``/etc/cpid.ini``, ``/usr/local/etc/cpid.ini``, or
``~/.cpid.ini``).


Synopsis
========

::

    cpid [-h] [--version] [-c CONFIG] [-q] [-v] [-l FILE] [-P] [-b ADDRESS]
         [-p PORT] [-d] [-u UID] [-g GID] [--pidfile FILE]


Description
===========

.. program: cpid

.. option:: -h, --help

    show this help message and exit

.. option:: --version

    show program's version number and exit

.. option:: -c CONFIG, --config CONFIG

    specify a configuration file to load

.. option:: -q, --quiet

    produce less console output

.. option:: -v, --verbose

    produce more console output

.. option:: -l FILE, --log-file FILE

    log messages to the specified file

.. option:: -P, --pdb

    run under PDB (debug mode)

.. option:: -b ADDRESS, --bind ADDRESS

    specifies the address to listen on for packets (default: 0.0.0.0)

.. option:: -p PORT, --port PORT

    specifies the UDP port for the server to listen on (default: 5647)

.. option:: -d, --daemon

    if specified, start as a background daemon

.. option:: -u UID, --user UID

    specifies the user that the daemon should run as. Defaults to the
    effective user (typically root)

.. option:: -g GID, --group GID

    specifies the group that the daemon should run as. Defaults to the
    effective group (typically root)

.. option:: --pidfile FILE

    specifies the location of the pid lock file


Usage
=====

The Compound Pi server is typically started at boot time by the init service.
The Raspbian package includes an init script for this purpose. Users on other
platforms will need to write their own init script.

When the server starts successfully it will initialize the camera and hold it
open.  This will prevent other applications from using the camera but also
makes it easy to see that the server has started as the camera's LED will be
lit (this is useful as Compound Pi servers are typically headless).

.. note::

    If you explicitly set a user and/or group for the daemon (with the
    :option:`-u` and :option:`-g` options), be aware that using the Pi's camera
    typically requires membership of the ``video`` group. Furthermore, the
    specified user and group must have the ability to create and remove the
    pid lock file.

