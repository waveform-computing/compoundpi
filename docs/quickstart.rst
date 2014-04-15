.. _quickstart:

===========
Quick Start
===========

By far the easiest method of configuring a fleet of Compound Pi servers is to
get a single Pi running the :ref:`Compound Pi daemon <cpid>` successfully,
using an automatic network configuration, then clone its SD card for all the
other Pis.

This quick start tutorial assumes you are using the Raspbian operating system
on your Pis, and Ubuntu as your client.

Server Network Configuration
============================

On Raspbian, to configure the Pi to use DHCP to automatically obtain an IP
address, edit the ``/etc/network/interfaces`` file and ensure that it looks
similar to the following::

    auto lo

    iface lo inet loopback
    iface eth0 inet dhcp

    allow-hotplug wlan0
    iface wlan0 inet manual
    wpa-roam /etc/wpa_supplicant/wpa_supplicant.conf
    iface default inet dhcp

This configuration should ensure that the first Ethernet and/or WiFi interfaces
will pick up an address automatically from the local DHCP server. To complete
the WiFi configuration, edit the ``/etc/wpa_supplicant/wpa_supplicant.conf``
file to look something like the following::

    ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
    update_config=1

    network={
            ssid="my_wireless_ssid"
            psk="my_wireless_password"
            proto=RSN
            key_mgmt=WPA-PSK
            pairwise=CCMP
            auth_alg=OPEN
    }

Server Daemon Installation
==========================

Execute the following command to install the Compound Pi server package and the
NTP daemon (the latter is required for time-synchronized image capture)::

    $ sudo apt-get install compoundpi-server ntp

This should pull in all necessary dependencies, and automatically install an
init-script which will start the Compound Pi daemon on boot-up. Test this by
rebooting the Pi with a camera module attached. You should see the camera
module's LED light up when the daemon starts. If it doesn't, the most likely
culprit is the camera: try running ``raspistill``, ensure you've activated the
camera with ``sudo raspi-config``, and ensure the CSI cable is inserted
correctly.

Clone the SD Card
=================

Once you've got a Pi running the Compound Pi daemon successfully, shut it down
and place its SD card in any Linux machine with an SD card reader. Unmount any
partitions that auto-mount, then figure out which device node represents the SD
card. For example, the following would tell you that the SD card is sdd::

    $ dmesg | tail | grep "Attached SCSI removable disk"
    [    3.428459] sd 8:0:0:0: [sdd] Attached SCSI removable disk

Clone the SD card into a disk file::

    $ sudo dd if=/dev/sdd of=server.img

This will take some considerable time to finish. Once it has done so, eject the
source SD card and insert the target one in its place. Remember to unmount any
partitions which auto-mount, then execute the reverse command::

    $ sudo dd if=server.img of=/dev/sdd

Repeat this last step for all remaining target cards. Finally, install the SD
cards in your set of Pi servers and boot them all to ensure their camera
modules activate.

.. warning::

    Ensure your target SD cards are the same size or larger than the source SD
    card. If they are larger, they will still appear the same size as the
    source after cloning because you the cloning also duplicates the partition
    table of the smaller device.

Client Installation
===================

Ensure your Ubuntu client machine is connected to the same network as your Pis
(whether by Ethernet or Wifi doesn't matter). Then, execute the following to
install the client::

    $ sudo add-apt-repository ppa:waveform/ppa
    $ sudo apt-get update
    $ sudo apt-get install compoundpi-client

Once installed, simply execute ``cpi`` to run the client. You will be presented
with a command line like the following::

    CompoundPi Client
    Type "help" for more information, or "find" to locate Pi servers
    cpi>

You can use the ``help`` command to discover the available commands, but as
suggested the first step in using your Compound Pi servers is to locate them on
the network. If you run ``find`` on its own it will send out a broadcast ping
and wait for a fixed number of seconds for servers to respond. If you know
exactly how many servers you have, specify a number with the ``find`` command
and it will warn you if it doesn't find that many servers (it will also finish
faster if it does find the expected number of Pis)::

    cpi> find 2
    Found 2 servers

You can query the status of your servers with the ``status`` command which will
give you the basics for the camera configuration, the time according to the
server, and the number of images currently stored in memory on the server. If
you only want to query a specific set of servers you can give their addresses
as a parameter::

    cpi> status 192.168.80.154
    Address        Resolution Framerate Timestamp                  Images
    -------------- ---------- --------- -------------------------- ------
    192.168.80.154 1280x720   30.00fps  2014-04-15 20:53:06.826477 0

To shoot an image, use the ``capture`` command::

    cpi> capture

Finally, to download the captured images from all Pis, simply use the ``download``
command::

    cpi> download
    Downloaded image 0 from 192.168.80.154
    Downloaded image 0 from 192.168.80.168

You can use the ``config`` and ``set`` commands to configure capture options,
the download target directory, and so on.
