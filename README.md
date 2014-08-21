VisualPRU
=========

VisualPRU is a minimal browser-based editor and debugger for the Beaglebone PRUs. The app runs from a local server on the Beaglebone and is accessed by connecting your Beaglebone to the local network(via a USB connection, ethernet, or wireless) and navigating your browser to **192.168.7.2:3333**. The hardware is accessed by twiddling bits in memory-mapped /dev/mem . Assembly programs are compiled using TI's open-source pasm library.

_Screenshot_
![screenshot](http://i.imgur.com/PhcfLR8.png)

* The Header allows you to choose which PRU you are targeting and shows their current status. If you're working on an application where the PRUs collaborate, it's possible to trigger a program on one PRU and debug the other PRU as they interact.
* Column 1 shows the editor view. You can add as many files as you want and include them in your main program(e.g. for header files and macro definitions).
* Column 2 shows the compiler view. It shows the output from the TI PASM compiler and allows you to step through your compiled code or run it full-speed.
* Column 3 shows the memory view. It allows you to look at the values of all the general purpose registers.

Installation
----
Install python if necessary, then:

```sh
pip install bottle
pip install gevent-websocket

cd /home
git clone https://github.com/mmcdan/visualpru.git
```
Finally, download [pasm], run the *linuxbuild* script, and put the resulting executable in /usr/local/bin (or another system-wide binary location)

Running
----
Just go into the VisualPRU directory and type **python visualpru.py**, then navigate to **192.168.7.2:3333** with your browser! To stop the program, use **CTRL-C**.

TODO
----
* Transition from /dev/mem to UIO
* Add the ability to load existing source files
* Highlight errors in the editor view
* Allow the user to modify memory registers
* Show Data RAM, Scratchpad RAM, and DDR RAM chunk in memory view
* Add better error-handling for edge cases
* Add unit tests

Known Issues
----
* Web interface layout is compressed when using Internet Explorer

License
----

MIT

[pasm]:https://github.com/beagleboard/am335x_pru_package/tree/master/pru_sw/utils/pasm_source
