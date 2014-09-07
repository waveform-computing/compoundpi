.. _commands:

===============
Client Commands
===============

Each section below documents one of the commands available in the Compound Pi
command line client. Many commands accept an address or list of addresses.
Addresses must be specified in dotted-decimal format (no hostnames). Inclusive
ranges of addresses are specified by two dash-separated addresses. Lists of
addresses, or ranges of addresses are specified by comma-separating each list
item.

The following table demonstrates various examples of this syntax:

+-----------------------------------------+-------------+
| Syntax                                  | Expands To  |
+=========================================+=============+
| ``192.168.0.1``                         | 192.168.0.1 |
+-----------------------------------------+-------------+
| ``192.168.0.1-192.168.0.5``             | 192.168.0.1 |
|                                         | 192.168.0.2 |
|                                         | 192.168.0.3 |
|                                         | 192.168.0.4 |
|                                         | 192.168.0.5 |
+-----------------------------------------+-------------+
| ``192.168.0.1,192.168.0.3``             | 192.168.0.1 |
|                                         | 192.168.0.3 |
+-----------------------------------------+-------------+
| ``192.168.0.1,192.168.0.3-192.168.0.5`` | 192.168.0.1 |
|                                         | 192.168.0.3 |
|                                         | 192.168.0.4 |
|                                         | 192.168.0.5 |
+-----------------------------------------+-------------+
| ``192.168.0.1-192.168.0.3,192.168.0.5`` | 192.168.0.1 |
|                                         | 192.168.0.2 |
|                                         | 192.168.0.3 |
|                                         | 192.168.0.5 |
+-----------------------------------------+-------------+

It is also worth noting that if readline is installed (which it is on almost
any modern Unix platform), the command line supports :kbd:`Tab`-completion for
commands and most parameters, including defined server addresses.


.. _command_add:

add
===

**Syntax:** add *addresses*

The :ref:`command_add` command is used to manually define the set of Pi servers
to communicate with. Addresses can be specified individually, as a
dash-separated range, or a comma-separated list of ranges and addresses.

See also: :ref:`command_find`, :ref:`command_remove`, :ref:`command_servers`.

::

  cpi> add 192.168.0.1
  cpi> add 192.168.0.1-192.168.0.10
  cpi> add 192.168.0.1,192.168.0.5-192.168.0.10


.. _command_awb:

awb
===

**Syntax:** awb (*mode* | *red_gain* *blue_gain*) *[addresses]*

The :ref:`command_awb` command is used to set the AWB mode of the camera on all
or some of the defined servers. The mode can be one of the following:

* auto
* cloudy
* flash
* fluorescent
* horizon
* incandescent
* shade
* sunlight
* tungsten

Alternatively you can specify the red and blue gains of the camera manually
as two floating point values. Valid gains for each channel are between 0.0
and 8.0. Typical values are between 1.0 and 2.0 (for most scenes, red gain
slightly exceeds blue gain, e.g. 1.6 and 1.2 respectively).

If no address is specified then all currently defined servers will be
targetted. Multiple addresses can be specified with dash-separated ranges,
comma-separated lists, or any combination of the two.

See also: :ref:`command_status`, :ref:`command_exposure`,
:ref:`command_metering`.

::

    cpi> awb auto
    cpi> awb 1.5 1.3
    cpi> awb fluorescent 192.168.0.1
    cpi> awb 1.7 1.0 192.168.0.10
    cpi> awb sunlight 192.168.0.1-192.168.0.10


.. _command_capture:

capture
=======

**Syntax:** capture *[addresses]*

The :ref:`command_capture` command causes the servers to capture an image. Note
that this does not cause the captured images to be sent to the client. See the
:ref:`command_download` command for more information.

If no addresses are specified, a broadcast message to all defined servers will
be used in which case the timestamp of the captured images are likely to be
extremely close together. If addresses are specified, unicast messages will be
sent to each server in turn.  While this is still reasonably quick there will
be a measurable difference between the timestamps of the last and first
captures.

See also: :ref:`command_download`, :ref:`command_clear`.

::

  cpi> capture
  cpi> capture 192.168.0.1
  cpi> capture 192.168.0.50-192.168.0.53


.. _command_clear:

clear
=====

**Syntax:** clear *[addresses]*

The :ref:`command_clear` command can be used to clear the in-memory image store
on the specified Pi servers (or all Pi servers if no address is given). The
:ref:`command_download` command automatically clears the image store after
successful transfers so this command is only useful in the case that the
operator wants to discard images without first downloading them.

See also: :ref:`command_download`, :ref:`command_capture`.

::

  cpi> clear
  cpi> clear 192.168.0.1-192.168.0.10



.. _command_config:

config
======

**Syntax:** config

The :ref:`command_config` command is used to display the current client
configuration. Use the related :ref:`command_set` command to alter the
configuration.

See also: :ref:`command_set`.

::

  cpi> config


.. _command_download:

download
========

**Syntax:** download *[addresses]*

The :ref:`command_download` command causes each server to send its captured
images to the client. Servers are contacted consecutively to avoid saturating
the network bandwidth. Once images are successfully downloaded from a server,
they are wiped from the server.

See also: :ref:`command_capture`, :ref:`command_clear`.

::

  cpi> download
  cpi> download 192.168.0.1



.. _command_exit:

exit
====

**Syntax:** exit|quit

The :ref:`command_exit` command is used to terminate the application. You can
also use the standard UNIX :kbd:`Ctrl+D` end of file sequence to quit.



.. _command_exposure:

exposure
========

**Syntax:** exposure *mode|speed* *[addresses]*

The :ref:`command_exposure` command is used to set the exposure mode or speed
of the camera on all or some of the defined servers. The mode can be one of the
following:

* antishake
* auto
* backlight
* beach
* fireworks
* fixedfps
* night
* nightpreview
* snow
* sports
* spotlight
* verylong

Alternatively you can specify an explicit exposure speed in milliseconds.  Note
that the exposure speed is limited by the framerate. Hence, if the camera's
framerate is currently 30fps then the exposure speed cannot be slower than
33.333ms (1000/30). Adjust framerate prior to adjusting exposure speed.

If no address is specified then all currently defined servers will be
targetted. Multiple addresses can be specified with dash-separated ranges,
comma-separated lists, or any combination of the two.

See also: :ref:`command_status`, :ref:`command_awb`, :ref:`command_metering`.

::

    cpi> exposure auto
    cpi> exposure 33.33
    cpi> exposure night 192.168.0.1
    cpi> exposure 60.00 192.168.0.10
    cpi> exposure backlight 192.168.0.1-192.168.0.10


.. _command_find:

find
====

**Syntax:** find *[count]*

The :ref:`command_find` command is typically the first command used in a client
session to locate all Pis on the configured subnet. If a count is specified,
the command will display an error if the expected number of Pis is not located.

See also: :ref:`command_add`, :ref:`command_remove`, :ref:`command_servers`,
:ref:`command_identify`.

::

  cpi> find
  cpi> find 20


.. _command_flip:

flip
====

**Syntax:** flip *value* *[addresses]*

The :ref:`command_flip` command is used to set the picture orientation on all
or some of the defined servers. The following values can be specified:

* none
* horizontal
* vertical
* both

If no address is specified then all currently defined servers will be
targetted. Multiple addresses can be specified with dash-separated ranges,
comma-separated lists, or any combination of the two.

See also: :ref:`command_status`.

::

    cpi> flip none
    cpi> flip vertical 192.168.0.1
    cpi> flip both 192.168.0.1-192.168.0.10


.. _command_framerate:

framerate
=========

**Syntax:** framerate *rate* *[addresses]*

The :ref:`command_framerate` command is used to set the capture framerate of
the camera on all or some of the defined servers. The rate can be specified as
an integer, a floating-point number, or as a fractional value. The framerate
of the camera influences the capture mode that the camera uses. See the
`camera hardware`_ chapter of the picamera documentation for more information.

If no address is specified then all currently defined servers will be
targetted. Multiple addresses can be specified with dash-separated ranges,
comma-separated lists, or any combination of the two.

See also: :ref:`command_status`, :ref:`command_resolution`.

::

  cpi> framerate 30
  cpi> framerate 90 192.168.0.1
  cpi> framerate 15 192.168.0.1-192.168.0.10

.. _camera hardware: http://picamera.readthedocs.org/en/latest/fov.html


.. _command_help:

help
====

**Syntax:** help *[command]*

The 'help' command is used to display the help text for a command or, if no
command is specified, it presents a list of all available commands along with
a brief description of each.


.. _command_identify:

identify
========

**Syntax:** identify *[addresses]*

The :ref:`command_identify` command can be used to locate a specific Pi server
(or servers) by their address. It sends a command causing the camera's LED to
blink on and off for 5 seconds. If no addresses are specified, the command will
be sent to all defined servers (this can be useful after the
:ref:`command_find` command to determine whether any Pi's failed to respond due
to network issues).

See also: :ref:`command_find`.

::

  cpi> identify
  cpi> identify 192.168.0.1
  cpi> identify 192.168.0.3-192.168.0.5


.. _command_iso:

iso
===

**Syntax:** iso *value* *[addresses]*

The :ref:`command_iso` command is used to set the emulated ISO value of the
camera on all or some of the defined servers. The value can be specified as an
integer number between 0 and 1600, or ``auto`` which leaves the camera to
determine the optimal ISO value.

If no address is specified then all currently defined servers will be
targetted. Multiple addresses can be specified with dash-separated ranges,
comma-separated lists, or any combination of the two.

See also: :ref:`command_status`, :ref:`command_exposure`.

::

    cpi> iso auto
    cpi> iso 100 192.168.0.1
    cpi> iso 800 192.168.0.1-192.168.0.10


.. _command_levels:

levels
======

**Syntax:** levels *brightness* *contrast* *saturation* *[addresses]*

The :ref:`command_levels` command is used to simultaneously set the brightness,
contrast, and saturation levels on all or some of the defined servers.  Each
level is specified as an integer number between 0 and 100. The default for each
level is 50.

If no address is specified then all currently defined servers will be
targetted. Multiple addresses can be specified with dash-separated ranges,
comma-separated lists, or any combination of the two.

See also: :ref:`command_status`.

::

    cpi> levels 50 50 50
    cpi> levels 70 50 50 192.168.0.1
    cpi> levels 40 60 70 192.168.0.1-192.168.0.10


.. _command_metering:

metering
========

**Syntax:** metering *mode* *[addresses]*

The :ref:`command_metering` command is used to set the metering mode of the
camera on all or some of the defined servers. The mode can be one of the
following:

* average
* backlit
* matrix
* spot

If no address is specified then all currently defined servers will be
targetted. Multiple addresses can be specified with dash-separated ranges,
comma-separated lists, or any combination of the two.

See also: :ref:`command_status`, :ref:`command_awb`, :ref:`command_exposure`.

::

    cpi> metering average
    cpi> metering spot 192.168.0.1
    cpi> metering backlit 192.168.0.1-192.168.0.10


.. _command_quit:

quit
====

**Syntax:** exit|quit

The :ref:`command_exit` command is used to terminate the application. You can
also use the standard UNIX :kbd:`Ctrl+D` end of file sequence to quit.


.. _command_remove:

remove
======

**Syntax:** remove *addresses*

The :ref:`command_remove` command is used to remove addresses from the set of
Pi servers to communicate with. Addresses can be specified individually, as a
dash-separated range, or a comma-separated list of ranges and addresses.

See also: :ref:`command_add`, :ref:`command_find`, :ref:`command_servers`.

::

  cpi> remove 192.168.0.1
  cpi> remove 192.168.0.1-192.168.0.10
  cpi> remove 192.168.0.1,192.168.0.5-192.168.0.10


.. _command_resolution:

resolution
==========

**Syntax:** resolution *width x height* *[addresses]*

The :ref:`command_resolution` command is used to set the capture resolution of
the camera on all or some of the defined servers. The resolution of the camera
influences the capture mode that the camera uses. See the `camera hardware`_
chapter of the picamera documentation for more information.

If no address is specified then all currently defined servers will be
targetted. Multiple addresses can be specified with dash-separated ranges,
comma-separated lists, or any combination of the two.

See also: :ref:`command_status`, :ref:`command_framerate`.

::

  cpi> resolution 640x480
  cpi> resolution 1280x720 192.168.0.54
  cpi> resolution 1280x720 192.168.0.1,192.168.0.3


.. _command_servers:

servers
=======

**Syntax:** servers

The :ref:`command_servers` command is used to list the set of servers that the
client expects to communicate with. The content of the list can be manipulated
with the :ref:`command_find`, :ref:`command_add`, and :ref:`command_remove`
commands.

See also: :ref:`command_find`, :ref:`command_add`, :ref:`command_remove`.

::

  cpi> servers


.. _command_set:

set
===

**Syntax:** set *name* *value*

The :ref:`command_set` command is used to alter the value of a client
configuration variable.  Use the related :ref:`command_config` command to view
the current configuration.

See also: :ref:`command_config`.

::

  cpi> set timeout 10
  cpi> set output ~/Pictures/
  cpi> set capture_count 5


.. _command_status:

status
======

**Syntax:** status *[addresses]*

The :ref:`command_status` command is used to retrieve configuration information
from servers. If no addresses are specified, then all defined servers will be
queried.

See also: :ref:`command_resolution`, :ref:`command_framerate`.

::

  cpi> status

