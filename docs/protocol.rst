.. _protocol:

================
Network Protocol
================

.. warning::

    As Compound Pi is a project in its infancy, the protocol version is
    currently the project's version and no attempt will be made to preserve
    backward (or forward) compatibility in the protocol until version 1.0 is
    released. In the current version, the client crudely compares the version
    in the :ref:`protocol_hello` response with its own version and rejects
    anything that doesn't match precisely.

The Compound Pi network protocol is UDP-based, utilizing broadcast or unicast
packets for commands, and unicast packets for responses. File transfers (as
initiated by the :ref:`command_download` command in the client) are TCP-based.
The diagram below shows a typical conversation between a Compound Pi client and
three servers involving a broadcast PING packet and the resulting responses:

.. image:: protocol_example.*
    :align: center

All messages are encoded as ASCII text.  Command messages consist of a non-zero
positive integer sequence number followed by a single space, followed by the
command in capital letters, optionally followed by space separated parameters
for the command. The following are all valid examples of command messages::

    1 HELLO 1400803122.359911

    2 CLEAR

    3 CAPTURE 1 0

    4 STATUS

    5 LIST

    6 SEND 0 5647

    7 FOO

In other words, the generic form of a command message is::

    <sequence-number> <command> [parameter1] [parameter2]...

Response messages (from the servers to the client) consist of a non-zero
positive integer sequence number (copied from the corresponding command),
followed by a single space, followed by :samp:`OK` if the command's execution
was successful, optionally followed by a new-line character (ASCII character
10), and any data the response is expected to include. For example::

    1 OK
    VERSION 0.3

    2 OK

    3 OK

    4 OK
    RESOLUTION 1280 720
    FRAMERATE 30
    AWB auto 1.5 1.3
    EXPOSURE auto 33.12 0
    ISO 0
    METERING average
    LEVELS 50 0 0
    FLIP 0 0
    TIMESTAMP 1400803173.991651
    IMAGES 1

    5 OK
    IMAGE 0 1400803173.012543 8083879

    6 OK

In the case of an error, the response message consists of a non-zero positive
integer sequence number (copied from the corresponding command), followed by a
single space, followed by :samp:`ERROR`, followed by a new-line character
(ASCII character 10), followed by a description of the error that occurred::

    7 ERROR
    Unknown command FOO

In other words, the general form of a response message is::

    <sequence-number> OK
    <data>

Or, if an error occurred::

    <sequence-number> ERROR
    <error-description>

Sequence numbers start at 1 (0 is reserved), and are incremented on each
command, except for :ref:`protocol_ack` and :ref:`protocol_hello`. The sequence
number for a response indicates which command the response is associated with
and likewise the sequence number for :ref:`protocol_ack` indicates the response
that the :ref:`protocol_ack` terminates. The :ref:`protocol_hello` command,
being the command that begins a session specifies a new starting sequence
number for the server.

As UDP is an unreliable protocol, some mechanism is required to compensate for
lost, unordered, or duplicated packets. All transmissions (commands and
responses) are repeated with random delays. The sequence number associated with
a client command permits servers to ignore repeated commands that they have
already seen. Likewise, the sequence number of the server response permits
clients to ignore repeated responses they have already seen.

Commands are repeated by the client until it has received a response from the
targetted server(s) (all located servers on the subnet in the case of broadcast
messages), or until a timeout has elapsed (5 seconds by default).

Responses are repeated by a server until it receives an ACK from the client
with a corresponding sequence number, or until a timeout has elapsed (5 seconds
by default).

An exception to the above is the :ref:`protocol_hello` command. Because this
command sets a new sequence number, servers cannot use the sequence number to
detect repeated packets. Hence, the :ref:`protocol_hello` command includes the
timestamp at the client issuing it as a command parameter. Servers must use
this timestamp to detect stale or repeated instances of this messsage. The
timestamp can be assumed to be incrementing (like a monotonic clock); in the
current implementation it isn't but this doesn't matter much given how rarely
this message is issued in a session.

Example
=======

In the following example, the client broadcasts a :ref:`protocol_hello` command
to three servers. The servers all respond with an OK response, but only the
packet from server1 makes it back to the client. The server resends the HELLO
command but this is ignored by the servers as they've seen the included
timestamp before. The client responds to server1 with an :ref:`protocol_ack`.
The other servers (after a random delay) now retry their OK responses and both
get through this time. The client responds with an ACK for server3, but the ACK
for server2 is lost. After another random delay, server2 once again retries its
OK response, causing the client to send another ACK which succeeds this time:

.. image:: protocol_retry.*
    :align: center

The following sections document the various commands that the server
understands and the expected responses.


.. _protocol_ack:

ACK
===

**Syntax:** ACK

The :ref:`protocol_ack` command is sent by the client to acknowledge receipt of
a response from a server. It is special in that its sequence number must match
the sequence number of the response that it acknowledges (it is the only
command that does not increment the sequence number on the client).

It is also special in that its implementation is effectively optional: a client
doesn't *have* to acknowledge receipt of a server's response; after 5 seconds,
the server will stop retrying its responses anyway, but an :ref:`protocol_ack`
command is nonetheless useful to reduce the congestion of the network with
useless response retries. It is also the only client message which is not
automatically repeated (as its only purpose is to silence the auto-repeating
of a response in order to reduce network congestion).

When a server receives the :ref:`protocol_ack` command, it must stop retrying
responses with the same sequence number as the ACK command. No other response
should be sent.


.. _protocol_agc:

AGC
===

**Syntax:** AGC *mode*

The :ref:`protocol_agc` command changes the camera's auto-gain-control mode
which is provided as a lower case string. If the string is ``'off'`` then
the current sensor analog and digital gains will be fixed at their present
values.

An OK response is expected with no data.


.. _protocol_awb:

AWB
===

**Syntax:** AWB *mode* *[red blue]*

The :ref:`protocol_awb` command changes the camera's auto-white-balance mode
which is provided as a lower case string. If the string is ``'off'`` then
manual red and blue gains may additionally be specified as floating point
values between 0.0 and 8.0.

An OK response is expected with no data.


.. _protocol_blink:

BLINK
=====

**Syntax:** BLINK

The :ref:`protocol_blink` command should cause the server to identify itself
for the purpose of debugging. In this implementation, this is accomplished by
blinking the camera's LED for 5 seconds.

An OK response is expected with no data.


.. _protocol_capture:

CAPTURE
=======

**Syntax:** CAPTURE *[count [video-port [sync]]]*

The :ref:`protocol_capture` command should cause the server to capture one or
more images from the camera. The parameters are as follows:

*count*
    Specifies the number of images to capture. If specified, this must be a
    non-zero positive integer number. If not specified, defaults to 1.

*video-port*
    Specifies which port to capture from. If unspecified, or 0, the still port
    should be used (resulting in the best quality capture, but may cause
    significant delay between multiple consecutive shots). If 1, the video
    port should be used.

*sync*
    Specifies the timestamp at which the capture should be taken. The
    timestamp's form is UNIX time: the number of seconds since the UNIX epoch
    specified as a dotted-decimal. The timestamp must be in the future, and it
    is important for the server's clock to be properly synchronized in order
    for this functionality to operate correctly. If unspecified, the capture
    should be taken immediately upon receipt of the command.

The image(s) taken in response to the command should be stored locally on the
server until their retrieval is requested by the :ref:`protocol_send` command.
The timestamp at which the image was taken must also be stored.  Storage in
this implementation is simply in RAM, but implementations are free to use any
storage medium they see fit.

An OK response is expected with no data.


.. _protocol_clear:

CLEAR
=====

**Syntax:** CLEAR

The :ref:`protocol_clear` command deletes all images from the server's local
storage.  As noted above in :ref:`protocol_capture`, implementations are free
to use any storage medium, but the current implementation simply uses a list in
RAM.

An OK response is expected with no data.


.. _protocol_exposure:

EXPOSURE
========

**Syntax:** EXPOSURE *mode* *[speed]*

The :ref:`protocol_exposure` command changes the camera's exposure mode, speed,
and compensation value. The mode is provided as a lower case string. If the
string is ``'off'``, the speed may additionally be specified as a floating
point number measured in milliseconds.

An OK response is expected with no data.


.. _protocol_flip:

FLIP
====

**Syntax:** FLIP *horizontal* *vertical*

The :ref:`protocol_flip` command changes the camera's orientation. The
horizontal and vertical parameters must be integer numbers which will be
interpreted as booleans (0 being false, anything else true).

An OK response is expected with no data.


.. _protocol_framerate:

FRAMERATE
=========

**Syntax:** FRAMERATE *num[/denom]*

The :ref:`protocol_framerate` command changes the camera's configuration to use
the specified framerate which is given either as an integer number between 1
and 90 or as a fraction consisting of an integer numerator and denominator
separated by a forward-slash.

An OK response is expected with no data.


.. _protocol_hello:

HELLO
=====

**Syntax:** HELLO *timestamp*

The :ref:`protocol_hello` command is sent by the client's :ref:`command_find`
command in order to locate Compound Pi servers. The server must send the
following string in the data portion of the OK response indicating the version
of the protocol that the server understands::

    VERSION 0.4

The server must use the sequence number of the command as the new starting
sequence number (i.e. HELLO resets the sequence number on the server). For this
reason, the sequence number cannot be used to detect repeated HELLO commands.
Instead the timestamp parameter should be used for this purpose: the timestamp
can be assumed to be incrementing hence HELLO commands from a particular host
with a timestamp less than or equal to one already seen can be ignored.


.. _protocol_iso:

ISO
===

**Syntax:** ISO *level*

The :ref:`protocol_iso` command changes the camera's emulated ISO level.  The
new level is provided as an integer number where 0 indicates automatic ISO
level.

An OK response is expected with no data.


.. _protocol_levels:

LEVELS
======

**Syntax:** LEVELS *brightness contrast saturation exposure_comp*

The :ref:`protocol_levels` command changes the camera's brightness, contrast,
saturation, and exposure compensation levels. The new levels are given as
integer numbers between 0 and 50 for brightness, -100 to 100 for contrast
and saturation, and -24 to 24 for exposure compensation (where increments of
6 represent 1 exposure stop).

An OK response is expected with no data.


.. _protocol_list:

LIST
====

**Syntax:** LIST

The :ref:`protocol_list` command causes the server to respond with a new-line
separated list detailing all locally stored images. Each line in the data
portion of the response has the following format::

    IMAGE <number> <timestamp> <size>

For example, if five images are stored on the server the data portion of the
OK response may look like this::

    IMAGE 0 1398618927.307944 8083879
    IMAGE 1 1398619000.53127 7960423
    IMAGE 2 1398619013.658935 7996156
    IMAGE 3 1398619014.122921 8061197
    IMAGE 4 1398619014.314919 8053651

The :samp:`number` portion of the line is a zero-based integer index for the
image which can be used with the :ref:`protocol_send` command to retrieve the
image data. The :samp:`timestamp` portion is in UNIX-time format: a
dotted-decimal value of the number of seconds since the UNIX epoch. Finally,
the :samp:`size` portion is an integer number indicating the number of bytes in
the image.


.. _protocol_metering:

METERING
========

**Syntax:** METERING *mode*

The :ref:`protocol_metering` command changes the camera's light metering mode.
The new mode is provided as a lower case string.

An OK response is expected with no data.


.. _protocol_resolution:

RESOLUTION
==========

**Syntax:** RESOLUTION *width* *height*

The :ref:`protocol_resolution` command changes the camera's configuration to
use the specified capture resolution which is two integer numbers giving the
width and height of the new resolution.

An OK response is expected with no data.


.. _protocol_send:

SEND
====

**Syntax:** SEND *index* *port*

The :ref:`protocol_send` command causes the specified image to be sent from the
server to the client. The parameters are as follows:

*index*
    Specifies the zero-based index of the image that the client wants the
    server to send. This must match one of the indexes output by the
    :ref:`protocol_list` command.

*port*
    Specifies the TCP port on the client that the server should connect to in
    order to transmit the image data. This is given as an integer number (never
    a service name).

Assuming *index* refers to a valid image index, the server must connect to the
specified TCP port on the client, send the bytes of the image, and finally
close the connection. The server must also send an OK response with no data.


.. _protocol_status:

STATUS
======

**Syntax:** STATUS

The :ref:`protocol_status` command causes the server to send the client
information about its current configuration. Specifically, the response must
contain the following lines in its data portion, in the order given below::

    RESOLUTION <width> <height>
    FRAMERATE <num>[/denom]
    AWB <awb_mode> <awb_red> <awb_blue>
    EXPOSURE <exp_mode> <exp_speed> <exp_comp>
    ISO <iso>
    METERING <metering_mode>
    LEVELS <brightness> <contrast> <saturation>
    FLIP <hflip> <vflip>
    TIMESTAMP <time>
    IMAGES <images>

Where:

*<width> <height>*
    Gives the camera's currently configured capture resolution

*<num>[/denom]*
    Gives the camera's currently configured framerate as an integer number or
    fractional value

*<awb_mode>*
    Gives the camera's current auto-white-balance mode as a lower case string

*<awb_red>*
    Gives the camera's red-gain as an integer number or fractional value

*<awb_blue>*
    Gives the camera's blue-gain as an integer number or fractional value

*<exp_mode>*
    Gives the camera's current exposure mode as a lower case string

*<exp_speed>*
    Gives the camera's current exposure speed as a floating point number
    measured in milliseconds.

*<exp_comp>*
    Gives the camera's current exposure compensation value as an integer
    number between -24 and 24 (each increment represents 1/6th of a stop)

*<iso>*
    Gives the camera's current ISO setting as an integer number between 0 and
    1600 (where 0 indicates automatic)

*<metering_mode>*
    Gives the camera's current light metering mode as a lower case string

*<brightness>*
    Gives the camera's current brightness setting as an integer value between
    0 and 100 (50 is the default)

*<contrast>*
    Gives the camera's current contrast setting as an integer between -100 and
    100 (0 is the default)

*<saturation>*
    Gives the camera's current saturation setting as an integer between -100 and
    100 (0 is the default)

*<hflip>* and *<vflip>*
    Gives the camera's orientation as 1 or 0 (indicating the flip is or is not
    active respectively)

*<time>*
    Gives the timestamp at which the :ref:`protocol_status` command was
    received in UNIX time format (a dotted-decimal number of seconds since the
    UNIX epoch).

*<images>*
    Gives the number of images currently stored locally by the server.

For example, the data portion of the OK response may look like the following::

    RESOLUTION 1280 720
    FRAMERATE 30
    AWB auto 321/256 3/2
    EXPOSURE auto 33.158 0
    ISO 0
    METERING average
    LEVELS 50 0 0
    FLIP 0 0
    TIMESTAMP 1400803173.991651
    IMAGES 1

