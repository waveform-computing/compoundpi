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

Client Installation
===================

Ensure your Ubuntu client machine is connected to the same network as your Pis
(whether by Ethernet or Wifi doesn't matter). Then, execute the following to
install the client and an NTP daemon::

    $ sudo add-apt-repository ppa:waveform/ppa
    $ sudo apt-get update
    $ sudo apt-get install compoundpi-client ntp

The NTP daemon will most likely be installed to synchronize with an NTP pool
on the Internet (e.g. :samp:`pool.ntp.org`). This is fine, but check that it's
working with the following command line::

    $ ntpq -p
         remote           refid      st t when poll reach   delay   offset  jitter
    ==============================================================================
    *aaaaaaa.aaaaaaa nn.nnn.nnn.nnn   3 u  109 1024  377    4.639   -2.101  21.233

Server Network Configuration
============================

On the Pi you intend to clone, configure networking to use DHCP to
automatically obtain an IP address. Edit the ``/etc/network/interfaces`` file
and ensure that it looks similar to the following::

    auto lo

    iface lo inet loopback
    iface eth0 inet dhcp

    allow-hotplug wlan0
    iface wlan0 inet manual
    wpa-roam /etc/wpa_supplicant/wpa_supplicant.conf
    iface default inet dhcp

This configuration should ensure that the first Ethernet and/or WiFi interfaces
will pick up an address automatically from the local DHCP server. If you are
using WiFi, complete the WiFi configuration by editing the
:file:`/etc/wpa_supplicant/wpa_supplicant.conf` file to look something like the
following::

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

Server Installation
===================

Execute the following command to install the Compound Pi server package and the
NTP daemon (the latter is required for time-synchronized image capture)::

    $ sudo apt-get install compoundpi-server ntp

This should pull in all necessary dependencies, and automatically install an
init-script which will start the Compound Pi daemon on boot-up. Test this by
rebooting the Pi with a camera module attached. You should see the camera
module's LED light up when the daemon starts. If it doesn't, the most likely
culprit is the camera: try running :command:`raspistill`, ensure you've
activated the camera with :command:`sudo raspi-config`, and ensure the CSI
cable is inserted correctly. You can control the Compound Pi daemon as you
would any other system daemon::

    $ sudo service cpid stop
    $ sudo service cpid start
    $ sudo service cpid restart

Ideally, you want all your Pi servers to sync with the NTP time server you set
up on your client. Edit the :file:`/etc/ntp.conf` file and repalce the
:samp:`server` lines with the IP address of your client (ideally you should
configure your router to give your client a fixed address)::

    ...
    #server 0.debian.pool.ntp.org iburst
    #server 1.debian.pool.ntp.org iburst
    #server 2.debian.pool.ntp.org iburst
    #server 3.debian.pool.ntp.org iburst
    server 192.168.1.2
    ...

Restart the NTP daemon to use the new configuration::

    $ sudo service ntp restart

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

Testing the Servers
===================

Back on the Ubuntu client machine, execute :ref:`cpi` to run the client.
You will be presented with a command line like the following::

    CompoundPi Client
    Type "help" for more information, or "find" to locate Pi servers
    cpi>

Firstly, ensure that the network configuration is correct. The
:ref:`command_config` command can be used to print the current configuration::

    cpi> config
    Setting       Value
    ------------- --------------
    network       192.168.0.0/16
    port          5647
    bind          0.0.0.0:5647
    timeout       5
    capture_delay 0
    capture_count 1
    video_port    False
    time_delta    0.25
    output        /tmp

Assuming we're using a typical home router which gives out addresses in the
192.168.1.x network, this is incorrect. In order for broadcasts to work, the
network *must* have the correct definition - it's no good having a superset
configured (192.168.0.0/16 is a superset of 192.168.1.0/24). To correct the
network definition, use the :ref:`command_set` command::

    cpi> set network 192.168.1.0/24
    cpi> config
    Setting       Value
    ------------- --------------
    network       192.168.1.0/24
    port          5647
    bind          0.0.0.0:5647
    timeout       5
    capture_delay 0
    capture_count 1
    video_port    False
    time_delta    0.25
    output        /tmp

To make permanent configuration changes, simply place them in a file named
``~/.cpi.ini`` like so::

    [cpi]
    network=192.168.1.0/24
    timeout=10
    output=~/Pictures

With the network configured correctly, you can now use :ref:`command_find` to
locate your servers.  If you run :ref:`command_find` on its own it will send
out a broadcast ping and wait for a fixed number of seconds for servers to
respond. If you know exactly how many servers you have, specify a number with
the :ref:`command_find` command and it will warn you if it doesn't find that
many servers (it will also finish faster if it does find the expected number of
Pis)::

    cpi> find 2
    Found 2 servers

You can query the status of your servers with the :ref:`command_status` command
which will give you the basics for the camera configuration, the time according
to the server, and the number of images currently stored in memory on the
server. If you only want to query a specific set of servers you can give their
addresses as a parameter::

    cpi> status 192.168.1.154
    Address        Resolution  Time                       #
    -------------- ----------- -------------------------- -
    192.168.80.154 1280x720@30 2014-04-26 13:44:53.400000 0

If any major discrepancies are detected (resolution, framerate, or timestamp),
the status command should notify you of them. The maximum discrepancy permitted
in the timestamp is configured with the ``time_delta`` configuration setting.

To shoot an image, use the :ref:`command_capture` command::

    cpi> capture

Finally, to download the captured images from all Pis, simply use the
:ref:`command_download` command::

    cpi> download
    Downloaded image 0 from 192.168.1.154
    Downloaded image 0 from 192.168.1.168

You can use the :ref:`command_config` and :ref:`command_set` commands to
configure capture options, the download target directory, and so on.

Troubleshooting
===============

Compound Pi provides some crude but effective tools for debugging problems. The
first is simply that the daemon activates the camera by default. If you see
a Pi server without the camera LED lit after boot-up, you know the daemon has
failed to start for some reason.

The :ref:`command_identify` command is the main debugging tool provided by
Compound Pi.  If specified without any further parameters it will cause all
discovered Pi servers to blink their camera LED for 5 seconds. Thus, if you run
this command immediately after :ref:`command_find` you can quickly locate any
Pi servers that were no discovered (typically this is due to misconfiguration
of the network).

If :ref:`command_identify` is specified with one or more addresses, it will
blink the LED on the specified Pi servers. This can be used to quickly figure
out which address corresponds to which Pi (useful when dynamic addressing is
used).

