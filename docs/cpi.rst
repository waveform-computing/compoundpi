.. _cpi:

===
cpi
===

This is the Compound Pi client application which provides a command line
interface through which you can query and interact with any Pi's running the
:ref:`Compound Pi daemon <cpid>` on your configured subnet. Use the ``help``
command within the application for information on the available commands.

The application can be configured via command line switches, a configuration
file (defaults to ``/etc/cpi.ini``, ``/usr/local/etc/cpi.ini``, or
``~/.cpid.ini``), or through the interactive command line itself.


Synopsis
========

::

    cpi [-h] [--version] [-c CONFIG] [-q] [-v] [-l FILE] [-P] [-o PATH]
        [-n NETWORK] [-p PORT] [-b ADDRESS:PORT] [-t SECS]
        [--capture-delay SECS] [--capture-count NUM] [--video-port]


Description
===========

.. program: cpi

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

.. option:: -o PATH, --output PATH

    specifies the directory that downloaded images will be written to (default:
    ``/tmp``)

.. option:: -n NETWORK, --network NETWORK

    specifies the network that the servers belong to (default: 192.168.0.0/16)

.. option:: -p PORT, --port PORT

    specifies the port that the servers will be listening on (default: 5647)

.. option:: -b ADDRESS:PORT, --bind ADDRESS:PORT

    specifies the address and port that the client listens on for downloads
    (default: 0.0.0.0:5647)

.. option:: -t SECS, --timeout SECS

    specifies the timeout (in seconds) for network transactions (default: 5)

.. option:: --capture-delay SECS

    specifies the delay (in seconds) used to synchronize captures. This must be
    less than the network timeout (default: 0)

.. option:: --capture-count NUM

    specifies the number of consecutive pictures to capture when requested
    (default: 1)

.. option:: --video-port

    if specified, use the camera's video port for rapid capture


Usage
=====

The first command in a Compound Pi session is usually ``find`` to locate the
servers on the specified subnet. If you know the number of servers available,
specify it as an argument to the ``find`` command which will cause the command
to return quicker in the case that all servers are found, or to warn you if
less than the expected number are located.

The ``status`` command can be used to check that all servers have an equivalent
camera configuration, and that time sync is reasonable.

The ``capture`` command is used to cause all located servers to capture an
image. After capturing, use the ``download`` command to transfer all captured
images to the client.

Finally, the ``help`` command can be used to query the available commands, and
to obtain help on an individual command.
