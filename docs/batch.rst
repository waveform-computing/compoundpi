.. _batch:

======================
Building batch clients
======================

While the command line (:ref:`cpi`) and GUI (:ref:`cpigui`) clients lend
themselves to interactive use, neither is suited for batch use. Thankfully, the
logic for communicating with Compound Pi camera servers is split out into its
own class (:class:`~compoundpi.client.CompoundPiClient`) which is used by both
clients.  The class is relatively simple to use, and also lends itself to
construction of batch scripts for controlling Compound Pi camera servers.

The following sections document the API of the class, and provide several
examples of batch scripts.

.. currentmodule:: compoundpi.client

CompoundPiClient
================

.. autoclass:: CompoundPiClient
    :members:

CompoundPiStatus
================

.. autoclass:: CompoundPiStatus(resolution, framerate, awb_mode, ...)
    :members:

CompoundPiImage
===============

.. autoclass:: CompoundPiImage(image, timestamp, size)
    :members:

Resolution
==========

.. autoclass:: Resolution(width, height)

Examples
========

The following example demonstrates instantiating a client which attempts to
find 10 Compound Pi servers on the 192.168.0.0/24 network. It configures all
servers to capture images at 720p, captures a single image and then downloads
the resulting images to the current directory, naming each image after the IP
address of the server that captured it. Finally, the script ensures it clears
all images from the servers::

    import io
    from compoundpi.client import CompoundPiClient

    client = CompoundPiClient()
    client.network = '192.168.0.0/24'
    client.find(10)
    assert len(client) == 10
    client.resolution(1280, 720)
    client.capture()
    try:
        for addr, images in client.list().items():
            for image in images:
                print('Downloading image from %s' % addr)
                with io.open('%s.jpg' % addr) as output:
                    client.download(addr, image.index, output)
    finally:
        client.clear()

The following example explicitly defines 5 servers, configures them with a
variety of settings, then causes them to capture 5 images in rapid succession
from their camera's video ports. The *delay* parameter of
:meth:`CompoundPiClient.capture` is used to synchronize the captures to a
specific timestamp (it is assumed the servers clocks are synchronized).
Finally, all images are downloaded into a series of :class:`in-memory streams
<io.BytesIO>` (it is assumed the client has sufficient RAM to make this
efficient)::

    import io
    from compoundpi.client import CompoundPiClient

    client = CompoundPiClient()
    client.network = '192.168.0.0/24'
    print('Define servers 192.168.0.2-192.168.0.6')
    for i in range(2, 7):
        client.add('192.168.0.%d' % i)
    assert len(client) == 5
    print('Configuring servers')
    client.resolution(1280, 720)
    client.framerate(24)
    client.awb('off', 1.5, 1.3)
    client.exposure('auto')
    client.iso(100)
    client.metering('spot')
    client.levels(50, 0, 0)
    print('Capturing 5 images on all servers after 0.25 second delay')
    client.clear()
    client.capture(5, True, 0.25)
    for addr, status in client.status().items():
        assert status.images == 5
    print('Downloading captures')
    captures = {}
    try:
        for addr, images in client.list().items():
            for image in images:
                print('Downloading capture %d from %s' % (image.index, addr))
                stream = io.BytesIO()
                captures.setdefault(addr, []).append(stream)
                client.download(addr, image.index, stream)
                stream.seek(0)
    finally:
        client.clear()

The following example uses the :attr:`CompoundPiStatus.timestamp` field to
determine whether the time on any of the discovered servers deviates from any
other server by more than 0.1 seconds::

    from compoundpi.client import CompoundPiClient

    client = CompoundPiClient()
    client.network = '192.168.0.0/24'
    client.find(10)
    assert len(client) == 10
    responses = client.status()
    min_time = min(status.timestamp for status in responses.values())
    for address, status in responses.items():
        if (status.timestamp - min_time).total_seconds() > 0.1:
            print(
                'Warning: time on %s deviates from minimum '
                'by >0.1 seconds' % address)

For more comprehensive examples, you may wish to browse the implementations of
the :ref:`cpi` and :ref:`cpigui` applications as these are built using the
:class:`CompoundPiClient` class.
