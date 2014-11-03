## TinajaGate

Gateway software for an xbee based home automation system.

- continuously reads the serial port from xbee radio stream
- dispatches incoming tcp packets to appropriate methods for processing in a separate thread.
- sends data to node-red tcp socket.

As is common...  a work in progress.

I've designed PCBs with up to 4 sensors each (temperature, humidity, light, pir, gas, etc).  The PCB accomodates an XBee radio (802.15.4, formerly Series 1).  This could be set up as simply as attaching a TMP36 to an XBee radio.

There is also a gateway device (like a raspberry pi) that has a Slice of Pi adapter to attach a central XBee radio.  

This code reads the data stream from all sensor board radios and sends it out on a tcp port; ideally to an instance of node-red for redirection to a charting application like Graphite, to a local data store, or to a remote data store like Xively, Thingspeak, data.sparkfun.com (phant).

Questions and feedback appreciated.
