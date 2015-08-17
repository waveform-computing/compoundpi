# vim: set et sw=4 sts=4 fileencoding=utf-8:

# Copyright 2014 Dave Hughes <dave@waveform.org.uk>.
#
# This file is part of compoundpi.
#
# compoundpi is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 2 of the License, or (at your option) any later
# version.
#
# compoundpi is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# compoundpi.  If not, see <http://www.gnu.org/licenses/>.

"""
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
command in capital letters, optionally followed by comma-separated parameters
for the command. The following are all valid examples of command messages::

    1 HELLO 1400803122.359911

    2 CLEAR

    3 CAPTURE 1,0

    4 STATUS

    5 LIST

    6 SEND 0,5647

    7 FOO

In other words, the generic form of a command message is::

    <sequence-number> <command> [parameter1],[parameter2],...

Response messages (from the servers to the client) consist of a non-zero
positive integer sequence number (copied from the corresponding command),
followed by a single space, followed by :samp:`OK` if the command's execution
was successful, optionally followed by a new-line character (ASCII character
10), and any data the response is expected to include. For example::

    1 OK
    VERSION 0.4

    2 OK

    3 OK

    4 OK
    RESOLUTION 1280,720
    FRAMERATE 30
    AWB auto,1.5,1.3
    AGC auto,2.3,1.0
    EXPOSURE auto,28196
    ISO 0
    METERING average
    BRIGHTNESS 50
    CONTRAST 0
    SATURATION 0
    FLIP 0 0
    EV 0
    FLIP 0,0
    DENOISE 1
    TIMESTAMP 1400803173.991651
    IMAGES 1

    5 OK
    IMAGE,0,1400803173.012543,8083879

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

.. # See doc_generator() at end of module for construction of remaining text
"""

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')
try:
    from itertools import izip as zip
except ImportError:
    pass


import re
import inspect
import fractions
from textwrap import dedent


class boolstr(int):
    def __new__(cls, value):
        if isinstance(value, str) and value.isdigit():
            return super(boolstr, cls).__new__(cls, 1 if int(value) else 0)
        return super(boolstr, cls).__new__(cls, 1 if value else 0)

    def __str__(self):
        return '1' if self else '0'

    def __repr__(self):
        return repr(bool(self))


class lowerstr(str):
    def __new__(cls, value):
        if isinstance(value, str):
            return super(lowerstr, cls).__new__(cls, value.lower())
        return super(lowerstr, cls).__new__(cls, value)


class limitedfrac(fractions.Fraction):
    def __new__(cls, value):
        return super(limitedfrac, cls).__new__(cls, value).limit_denominator(65536)


def handler(command, *params):
    def decorator(f):
        argspec = inspect.getargspec(f)
        assert argspec.varargs is None
        assert argspec.keywords is None
        assert len(argspec.args) == len(params) + 1 # account for self
        f.command = command
        f.params = params
        return f
    return decorator


class CompoundPiProtocol(object):
    request_re = re.compile(
            r'(?P<seqno>\d+) '
            r'(?P<command>[A-Z]+)( (?P<params>.+))?')
    response_re = re.compile(
            r'(?P<seqno>\d+) '
            r'(?P<result>[A-Z]+)(\n(?P<data>.+))?', flags=re.DOTALL)

    """
    This abstract base class describes the Compound Pi protocol. The class
    itself is never directly used but various class functions are defined
    to transform it into useful forms.

    For example, at the end of this unit a function generates the protocol
    documentation (as module docs) from this class. In the server module,
    a class decorator converts it into a parser and dispatcher. In the client
    module, a function generates a formatter from it.

    Naturally, this is the first place that extensions to the protocol should
    be made. For each new command, define an empty method decorated with the
    @handler decorator. This accepts the command name, and types of each
    argument for the command. The method itself must define an equivalent
    number of arguments (excluding self) which may or may not have defaults
    (pure *args and **kwargs are not permitted in the interests of keeping the
    protocol simple).
    """

    @handler('HELLO', float)
    def do_hello(self, timestamp):
        """
        The :ref:`protocol_hello` command is sent by the client's
        :ref:`command_find` command in order to locate Compound Pi servers. The
        server must send the following string in the data portion of the OK
        response indicating the version of the protocol that the server
        understands::

            VERSION 0.4

        The server must use the sequence number of the command as the new
        starting sequence number (i.e. HELLO resets the sequence number on the
        server). For this reason, the sequence number cannot be used to detect
        repeated HELLO commands.  Instead the timestamp parameter should be
        used for this purpose: the timestamp can be assumed to be incrementing
        hence HELLO commands from a particular host with a timestamp less than
        or equal to one already seen can be ignored.
        """
        raise NotImplementedError

    @handler('BLINK')
    def do_blink(self):
        """
        The :ref:`protocol_blink` command should cause the server to identify
        itself for the purpose of debugging. In this implementation, this is
        accomplished by blinking the camera's LED for 5 seconds.

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('STATUS')
    def do_status(self):
        """
        The :ref:`protocol_status` command causes the server to send the client
        information about its current configuration. Specifically, the response
        must contain the following lines in its data portion, in the order
        given below::

            RESOLUTION <width>,<height>
            FRAMERATE <rate>
            AWB <awb_mode>,<awb_red>,<awb_blue>
            AGC <agc_mode>,<agc_analog>,<agc_digital>
            EXPOSURE <exp_mode>,<exp_speed>
            ISO <iso>
            METERING <metering_mode>
            BRIGHTNESS <brightness>
            CONTRAST <contrast>
            SATURATION <saturation>
            EV <ev>
            FLIP <hflip>,<vflip>
            DENOISE <denoise>
            TIMESTAMP <time>
            IMAGES <images>

        Where:

        *<width> <height>*
            Gives the camera's currently configured capture resolution

        *<rate>*
            Gives the camera's currently configured framerate as an integer
            number or fractional value (num/denom)

        *<awb_mode>*
            Gives the camera's current auto-white-balance mode as a lower case
            string

        *<awb_red>*
            Gives the camera's red-gain as an integer number or fractional
            value

        *<awb_blue>*
            Gives the camera's blue-gain as an integer number or fractional
            value

        *<agc_mode>*
            Gives the camera's current auto-gain-control mode as a lower case
            string

        *<agc_analog>*
            Gives the camera's current analog gain as a floating point value

        *<agc_digital>*
            Gives the camera's current digital gain as a floating point value

        *<exp_mode>*
            Gives the camera's current exposure mode as a lower case string

        *<exp_speed>*
            Gives the camera's current exposure speed as a floating point
            number measured in milliseconds.

        *<iso>*
            Gives the camera's current ISO setting as an integer number between
            0 and 1600 (where 0 indicates automatic)

        *<metering_mode>*
            Gives the camera's current light metering mode as a lower case
            string

        *<brightness>*
            Gives the camera's current brightness setting as an integer value
            between 0 and 100 (50 is the default)

        *<contrast>*
            Gives the camera's current contrast setting as an integer between
            -100 and 100 (0 is the default)

        *<saturation>*
            Gives the camera's current saturation setting as an integer between
            -100 and 100 (0 is the default)

        *<ev>*
            Gives the camera's current exposure compensation value as an
            integer number between -24 and 24 (each increment represents 1/6th
            of a stop)

        *<hflip>* and *<vflip>*
            Gives the camera's orientation as 1 or 0 (indicating the flip is or
            is not active respectively)

        *<denoise>*
            Gives the camera's software denoise status as 1 or 0 (indicating
            denoise is active or not respectively)

        *<time>*
            Gives the timestamp at which the :ref:`protocol_status` command was
            received in UNIX time format (a dotted-decimal number of seconds
            since the UNIX epoch).

        *<images>*
            Gives the number of images currently stored locally by the server.

        For example, the data portion of the OK response may look like the
        following::

            RESOLUTION 1280 720
            FRAMERATE 30
            AWB auto 321/256 3/2
            AGC auto 8.0 1.5
            EXPOSURE auto 33.158
            ISO 0
            METERING average
            BRIGHTNESS 50
            CONTRAST 0
            SATURATION 0
            EV 0
            FLIP 0 0
            DENOISE 1
            TIMESTAMP 1400803173.991651
            IMAGES 1
        """
        raise NotImplementedError

    @handler('RESOLUTION', int, int)
    def do_resolution(self, width, height):
        """
        The :ref:`protocol_resolution` command changes the camera's
        configuration to use the specified capture resolution which is two
        integer numbers giving the width and height of the new resolution.

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('FRAMERATE', limitedfrac)
    def do_framerate(self, rate):
        """
        The :ref:`protocol_framerate` command changes the camera's
        configuration to use the specified framerate which is given either as
        an integer number between 1 and 90 or as a fraction consisting of an
        integer numerator and denominator separated by a forward-slash.

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('AWB', lowerstr, limitedfrac, limitedfrac)
    def do_awb(self, mode, red=fractions.Fraction(1.0), blue=fractions.Fraction(1.0)):
        """
        The :ref:`protocol_awb` command changes the camera's auto-white-balance
        mode which is provided as a lower case string. If the string is
        ``'off'`` then manual red and blue gains may additionally be specified
        as floating point values between 0.0 and 8.0.

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('AGC', lowerstr)
    def do_agc(self, mode):
        """
        The :ref:`protocol_agc` command changes the camera's auto-gain-control
        mode which is provided as a lower case string. If the string is
        ``'off'`` then the current sensor analog and digital gains will be
        fixed at their present values.

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('EXPOSURE', lowerstr, float)
    def do_exposure(self, mode, speed):
        """
        The :ref:`protocol_exposure` command changes the camera's exposure
        mode, speed, and compensation value. The mode is provided as a lower
        case string. If the string is ``'off'``, the speed may additionally be
        specified as a floating point number measured in milliseconds.

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('METERING', lowerstr)
    def do_metering(self, mode):
        """
        The :ref:`protocol_metering` command changes the camera's light
        metering mode.  The new mode is provided as a lower case string.

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('ISO', int)
    def do_iso(self, iso):
        """
        The :ref:`protocol_iso` command changes the camera's emulated ISO
        level.  The new level is provided as an integer number where 0
        indicates automatic ISO level.

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('BRIGHTNESS', int)
    def do_brightness(self, brightness):
        """
        The :ref:`protocol_brightness` command changes the camera's brightness.
        The new level is given as an integer number between 0 and 100 (default
        50).

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('CONTRAST', int)
    def do_contrast(self, contrast):
        """
        The :ref:`protocol_contrast` command changes the camera's contrast. The
        new level is given as an integer number between -100 and 100 (default
        0).

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('SATURATION', int)
    def do_saturation(self, saturation):
        """
        The :ref:`protocol_saturation` command changes the camera's saturation.
        The new level is given as an integer number between -100 and 100
        (default 0).

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('EV', int)
    def do_ev(self, ev):
        """
        The :ref:`protocol_saturation` command changes the camera's exposure
        compensation (EV). The new level is given as an integer number between
        -24 and 24 where increments of 6 represent one exposure stop.

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('DENOISE', boolstr)
    def do_denoise(self, denoise):
        """
        The :ref:`protocol_denoise` command changes whether the camera's
        software denoise algorithm is active (for both images and video). The
        new value is given as an integer which represents a boolean (0 being
        false, and anything else interpreted as true).

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('FLIP', boolstr, boolstr)
    def do_flip(self, horizontal, vertical):
        """
        The :ref:`protocol_flip` command changes the camera's orientation. The
        horizontal and vertical parameters must be integer numbers which will
        be interpreted as booleans (0 being false, anything else true).

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('CAPTURE', int, boolstr, int, float)
    def do_capture(self, count=1, use_video_port=False, quality=None, sync=None):
        """
        The :ref:`protocol_capture` command should cause the server to capture
        one or more images from the camera. The parameters are as follows:

        *count*
            Specifies the number of images to capture. If specified, this must
            be a non-zero positive integer number. If not specified, defaults
            to 1.

        *video-port*
            Specifies which port to capture from. If unspecified, or 0, the
            still port should be used (resulting in the best quality capture,
            but may cause significant delay between multiple consecutive
            shots). If 1, the video port should be used.

        *quality*
            Specifies the quality of the encoding. Valid values are 1 to 100
            for ``jpeg`` encoding (larger is better).

        *sync*
            Specifies the timestamp at which the capture should be taken. The
            timestamp's form is UNIX time: the number of seconds since the UNIX
            epoch specified as a dotted-decimal. The timestamp must be in the
            future, and it is important for the server's clock to be properly
            synchronized in order for this functionality to operate correctly.
            If unspecified, the capture should be taken immediately upon
            receipt of the command.

        The image(s) taken in response to the command should be stored locally
        on the server until their retrieval is requested by the
        :ref:`protocol_send` command.  The timestamp at which the image was
        taken must also be stored.  Storage in this implementation is simply in
        RAM, but implementations are free to use any storage medium they see
        fit.

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('RECORD', float, lowerstr, int, int, int, boolstr, float)
    def do_record(self, length, format='h264', quality=0, bitrate=17000000,
            intra_period=None, motion_output=False, sync=None):
        """
        The :ref:`protocol_record` command should cause the server to record a
        video for *length* seconds from the camera. The parameters are as
        follows:

        *length*
            Specifies the length of time to record for as a non-zero floating
            point number.

        *format*
            Specifies the encoding to use. Valid values are ``mjpeg`` and
            ``h264``.

        *quality*
            Specifies the quality of the encoding. If unspecified or zero, a
            suitable default will be selected for the specified encoding. Valid
            values are 1 to 40 for ``h264`` encoding (smaller is better), and 1
            to 100 for ``mjpeg`` encoding (larger is better).

        *bitrate*
            Specifies the bitrate limit for the video encoder. Defaults to
            17000000 if unspecified.

        *sync*
            Specifies the timestamp at which the recording should begin. The
            timestamp's form is UNIX time: the number of seconds since the UNIX
            epoch specified as a dotted-decimal. The timestamp must be in the
            future, and it is important for the server's clock to be properly
            synchronized in order for this functionality to operate correctly.
            If unspecified, the recording should begin immediately upon receipt
            of the command.

        *intra-period*
            Only valid if format is ``h264``. Specifies the number of frames in
            a GOP (group of pictures), the first of which must be a keyframe
            (I-frame).  Defaults to 30 if unspecified.

        *motion-output*
            Only valid if format is ``h264``. If unspecified or 0, only video
            data is output. If 1, motion estimation vector data is also
            recorded as a separate file with an equivalent timestamp to the
            corresponding video data.

        The video recorded in response to the command should be stored locally
        on the server until its retrieval is requested by the
        :ref:`protocol_send` command.  The timestamp at which the recording was
        started must be stored. Storage in this implementation is simply in
        RAM, but implementations are free to use any storage medium they see
        fit.

        An OK response is expected with no data.
        """
        raise NotImplementedError

    @handler('SEND', int, int)
    def do_send(self, file_num, port):
        """
        The :ref:`protocol_send` command causes the specified file to be sent
        from the server to the client. The parameters are as follows:

        *index*
            Specifies the zero-based index of the file that the client wants
            the server to send. This must match one of the indexes output by
            the :ref:`protocol_list` command.

        *port*
            Specifies the TCP port on the client that the server should connect
            to in order to transmit the data. This is given as an integer
            number (never a service name).

        Assuming *index* refers to a valid image file, the server must connect
        to the specified TCP port on the client, send the bytes of the file,
        and finally close the connection. The server must also send an OK
        response with no data.
        """
        raise NotImplementedError

    @handler('LIST')
    def do_list(self):
        """
        The :ref:`protocol_list` command causes the server to respond with a
        new-line separated list detailing all locally stored files. Each line
        in the data portion of the response has the following format::

            <filetype>,<number>,<timestamp>,<size>

        For example, if four images and one video are stored on the server the
        data portion of the OK response may look like this::

            IMAGE,0,1398618927.307944,8083879
            IMAGE,1,1398619000.53127,7960423
            IMAGE,2,1398619013.658935,7996156
            IMAGE,3,1398619014.122921,8061197
            VIDEO,4,1398619014.314919,28053651

        The filetype will be ``IMAGE``, ``VIDEO``, or ``MOTION`` depending on
        the type of data contained within.

        The :samp:`number` portion of the line is a zero-based integer index
        for the image which can be used with the :ref:`protocol_send` command
        to retrieve the image data. The :samp:`timestamp` portion is in
        UNIX-time format: a dotted-decimal value of the number of seconds since
        the UNIX epoch. Finally, the :samp:`size` portion is an integer number
        indicating the number of bytes in the image.
        """
        raise NotImplementedError

    @handler('CLEAR')
    def do_clear(self):
        """
        The :ref:`protocol_clear` command deletes all images from the server's
        local storage.  As noted above in :ref:`protocol_capture`,
        implementations are free to use any storage medium, but the current
        implementation simply uses a list in RAM.

        An OK response is expected with no data.
        """
        raise NotImplementedError


def doc_generator(cls):
    def handler_docs(fn):
        assert inspect.isfunction(fn)
        argspec = inspect.getargspec(fn)
        if argspec.defaults is None:
            first_default = len(fn.params)
        else:
            first_default = len(fn.params) - len(argspec.defaults)
        return """\
.. _protocol_{command_lower}:

{command}
{underline}

**Syntax:** {command} {params}
{original_docs}
""".format(
                    original_docs=dedent(fn.__doc__ or ''),
                    command=fn.command,
                    underline='='*len(fn.command),
                    command_lower=fn.command.lower(),
                    params=',\\ '.join(
                        '*%s*' % argspec.args[i + 1]
                        if i < first_default else
                        '*[%s]*' % argspec.args[i + 1]
                        for i, param in enumerate(fn.params))
                    )

    return __doc__ + '\n' + '\n'.join(
        handler_docs(fn)
        for name, fn in sorted(cls.__dict__.items())
        if hasattr(fn, 'command')
        )

__doc__ = doc_generator(CompoundPiProtocol)
del doc_generator
