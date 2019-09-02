# ZWarePython
Python Code to interface with Z-Ware and to AWS MQTT

This is a simple code that interface with Z-Ware code on a RPI3 and will send / receive message to the AWS MQTT broker.

The code is not fully completed, but only proven the necessary funtionality

Original ZWarePython code is from here : https://github.com/Z-WavePublic/PyZWare/blob/master/zwareClient.py

In my code, I had removed all the network functions as I found it to be unstable. The code I had is purely for controlling devices
and receiving information from the devices and send to MQTT broker.

Please change the zwareClient.py to input your own AWS broker information and certificate.
