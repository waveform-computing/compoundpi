.. _changelog:

==========
Change log
==========


Release 0.4 (2015-08-24)
========================

Major enhancements in this release:

* Fixed bug where restarting client quickly after quit would fail (`#21`_)
* Added an officially documented batch interface (`#22`_)
* Added ability to control denoise algorithm on servers (`#23`_)
* Added video support to the protocol (accessible from command line and
  batch client, but not GUI) (`#24`_)
* Added ability to copy settings from one server to all others (`#25`_)
* Added ability to order servers; supported in all clients but only really
  useful in the batch client currently (`#26`_)
* Added ability to configure quality of captures (`#29`_)

.. _#21: https://github.com/waveform80/compoundpi/issues/21
.. _#22: https://github.com/waveform80/compoundpi/issues/22
.. _#23: https://github.com/waveform80/compoundpi/issues/23
.. _#24: https://github.com/waveform80/compoundpi/issues/24
.. _#25: https://github.com/waveform80/compoundpi/issues/25
.. _#26: https://github.com/waveform80/compoundpi/issues/26
.. _#29: https://github.com/waveform80/compoundpi/issues/29


Release 0.3 (2014-05-23)
========================

Several major enhancements in this release:

* A GUI client (cpigui) is now included. This is currently undocumented, but
  should be pretty intuitive to anyone familiar with the command line
  interface (`#3`_)
* Both clients and the server now support many more camera settings including
  white-balance, exposure, ISO, shutter speed, etc (`#12`_)
* All UDP messages (client and server) are now retried to ensure reliability,
  particularly during multiple unicast messages (`#13`_)

.. _#3: https://github.com/waveform80/compoundpi/issues/3
.. _#12: https://github.com/waveform80/compoundpi/issues/12
.. _#13: https://github.com/waveform80/compoundpi/issues/13


Release 0.2 (2014-04-27)
========================

Several improvements in this release:

* The network protocol has been changed to enhance its reliability when dealing
  with lots of Pis on unreliable networks (like Wifi)
* The status command has been enhanced to warn of configuration discrepancies.
* Lots more work on the docs


Release 0.1 (2014-04-15)
========================

Initial release
