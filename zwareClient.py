#Copyright 2014-2018 Silicon Laboratories Inc.
#The licensor of this software is Silicon Laboratories Inc.  Your use of this software is governed by the terms of  Silicon Labs Z-Wave Development Kit License Agreement.
#A copy of the license is available at www.silabs.com.

# author : aikhong
# Modify from original Silab code to add in MQTT connection to AWS
# Remove all network functions
# add in support for Thermostat control - 1 Nov 2019
# Formalize JSON format

from tkinter import *
from tkinter import messagebox
from zware import *
from threading import Thread
#aikhong
import sys
import ssl
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import json
import xml.etree.ElementTree as ET

import time
import string

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#aikhong
#mqtt topic settings
TOPIC_OF_SUBSCRIBE = "sgoffice/cmd"
TOPIC_OF_PUBLISH  = "sgoffice/update"

mqttc = AWSIoTMQTTClient("RPI_Zware")

sensor_event=[[],[0]]
binary_event=[[],[0]]
multilevel_sensor_event=[[],0]

Znodeid=[]
#for updating the device status
status = "none"
nodeid = 0
value = 0
type = 0
message = "none"

def json_encode(string):
	return json.dumps(string)

mqttc.json_encode=json_encode

def send(topic):
	print ("Message " +message )
	mqttc.publish(topic, message, 0)
	#print ("Message to AWS Published")

#aikhong - mqtt subscribe callback
def customCallback(client, userdata, message):
	global status, nodeid, value, type

	print("Handle_mqtt_message")
	print(message.payload)
	print("from topic: " +message.topic)
	print("--------------\n")
	m_decode=str(message.payload.decode("utf-8","ignore"))
	#m_decode=str(message.payload.decode())
	m_in=json.loads(m_decode) #decode json data
	#print(type(m_in))
	#JSON format :
	#{
	#	"nodeid" : "?",
	#	"command" : "<refer to command class",
	#	"value" : "?"
	#	"type" : "?"	// in some cases, may not be for all
	#}
	if(message.topic == "sgoffice/cmd"):
		#nodeid = m_in["nodeid"]
		nodeid = m_in["nodeid"]
		command = m_in["command"]
		value = m_in["value"]

		if(m_in["command"] == "switch" ):
			status = "binary"
			#print("Binary Switch Cmd")
			#binary_switch_action(nodeid, value)	cannot call from here

		if(m_in["command"] =="thermostat setpoint setting"):
			type = m_in["type"]
			status ="thermostat setpoint"
			#print("Thermostat setpoint Cmd")

		#debugging
		#print("Value = ",value)
		#print("Command =",command)
		#print("Type", type)


class zwareClientClass:
	BINARYSWITCHINTERFACE = 37
	BINARYSENSORINTERFACE = 48
	MULTILEVELSENSORINTERFACE = 49
	#aikhong
	NOTIFICATIONINTERFACE = 113
	THERMOSTATSETPOINTINTERFACE = 67
	#aikhong
	MAXSMARTSTARTDEVICES = 32
	runPollingThread = True
	debugData = None
	binarySwitchButton = None
	smartStartList = {}
	smartStartData = {}
	deviceDictionaryList = {}
	deviceInterfaceList = [BINARYSWITCHINTERFACE,BINARYSENSORINTERFACE,MULTILEVELSENSORINTERFACE,NOTIFICATIONINTERFACE, THERMOSTATSETPOINTINTERFACE]
	#deviceInterfaceList = [BINARYSWITCHINTERFACE,BINARYSENSORINTERFACE,MULTILEVELSENSORINTERFACE]	#original
	zware = None


	def __init__(self,zwareObject):
		self.zware = zwareObject
		for interface in self.deviceInterfaceList:
			self.deviceDictionaryList[interface] = {}
			self.deviceDictionaryList[interface]['defaultState'] = -1
			self.deviceDictionaryList[interface]['foundDevice'] = 0
			self.deviceDictionaryList[interface]['tempFoundDevice'] = 0
			self.deviceDictionaryList[interface]['previouslyFoundDevice'] = 0
			self.deviceDictionaryList[interface]['ifdDevice'] = 0
			#aikhong
			self.deviceDictionaryList[interface]['ZWnode'] = 0
			#aikhong

	##
	#\addtogroup connect
	#@{
	#\section modes Connection Modes
	#The user can either connect to the board(<b>Board Connection</b>) or to the portal(<b>Portal Connection</b>.) Selecting either opens a login frame based on the input type.<br>
	#\subsection board Board Connection
	#In this selection the user is communicating with ZWare in local mode i.e.,talking to ZWare in the board directly. In order to login to the server the user has to know it's IP address. The username and password is constant and hard-coded in the application. Once the user has entered a valid IP address the application will connect to the server.
	#\subsection portal Portal Connection
	#In this selection the user is communicating with the ZWare in portal mode i.e.,talking to the ZWare via a portal. In order to login the server the user should have registered a username and password with the server and configured it to connect to the zipgateway. The default URL for connecting in portal mode is <b>z-ware.silabs.com</b>. Once the user has entered a valid username and password the application will connect to the server.<br><br>On successfully connecting to the server in either mode the Application will display the current version of ZWare followed a list of nodes currently connected to the server.
	#@}
	def main_window(self,TK):
		initialFrame = self.create_frame(TK)
		buttonFrame = self.create_frame(TK)
		debugFrame = self.create_frame(TK)
		self.debugData = self.create_text(debugFrame,0,0)
		userScrollBar = self.create_scrollbar(debugFrame,0,1)
		userScrollBar.configure(command=self.debugData.yview)
		self.debugData['yscrollcommand'] = userScrollBar.set
		boardConnection = self.create_button("Board Connection",initialFrame,0,0)
		boardConnection.configure(command = lambda: self.connection_start(initialFrame,buttonFrame,"board"))
		portalConnection = self.create_button("Portal Connection",initialFrame,0,1)
		portalConnection.configure(command = lambda: self.connection_start(initialFrame,buttonFrame,"portal"))

	def connection_start(self,initialFrame,buttonFrame,connectionType):
		self.disable_frame(initialFrame)
		if connectionType == "board":
			boardIpName = self.create_label("Board IP address",buttonFrame,0,0)
			boardIpData = self.create_entry(buttonFrame,0,1)
			boardConnect = self.create_button("Connect",buttonFrame,1,0)
			boardConnect.configure(command = lambda: self.connected_to_server(boardConnect,buttonFrame,boardIpData.get()))
			close = self.create_button("Close connection",buttonFrame,1,1)
			close.configure(command = lambda: self.close_connection(boardConnect,initialFrame,buttonFrame))
		elif connectionType == "portal":
			self.debugData.insert(INSERT,"Portal URL is z-ware.silabs.com\n")
			portalUsername = self.create_label("Username",buttonFrame,0,0)
			portalUsernameData = self.create_entry(buttonFrame,0,1)
			portalPassword = self.create_label("Password",buttonFrame,1,0)
			portalPasswordData = self.create_entry(buttonFrame,1,1)
			portalPasswordData.configure(show="*")
			portalConnect = self.create_button("Connect",buttonFrame,2,0)
			portalConnect.configure(command = lambda: self.connected_to_server(portalConnect,buttonFrame,"z-ware.silabs.com",portalUsernameData.get(),portalPasswordData.get()))
			close = self.create_button("Close connection",buttonFrame,2,1)
			close.configure(command = lambda: self.close_connection(portalConnect,initialFrame,buttonFrame))


	def connected_to_server(self,Button,Frame,ipAddress,username="user",password="smarthome"):
		#if ipAddress == "": #temp solution
		#	self.debugData.delete('1.0', END)
		#	self.debugData.insert(INSERT, "Please enter a valid IP address\n")
		#	return
		#boardIp = 'https://' + ipAddress + '/'
		ipAddress ="192.168.10.54"	#aikhong - save time

		boardIp = 'https://' + ipAddress + '/'
		r = self.zware.zw_init(boardIp,username,password)
		v = r.findall('./version')[0]
		loginOutput = "Connected to zware version: " + v.get('app_major') + '.' + v.get('app_minor') + '\n'
		self.debugData.insert(INSERT, loginOutput)
		Button['state'] = 'disabled'
		# remove all nw functions
		#includeDevice = self.create_button("Include Device",Frame,3,0)
		#includeDevice.configure(command = lambda: self.device_inclusion(includeDevice))
		#includeDeviceSecurely = self.create_button("Include S2 Device",Frame,3,1)
		#includeDeviceSecurely.configure(command = lambda: self.device_inclusion_secure(includeDeviceSecurely))
		#excludeDevice = self.create_button("Exclude Device",Frame,5,0)
		#excludeDevice.configure(command = lambda:  self.device_exclusion(excludeDevice))
		#getNodeList = self.create_button("Node details",Frame,5,1)
		getNodeList = self.create_button("Node details",Frame,3,0)
		getNodeList.configure(command = lambda: self.node_list_action())
		#smartStart = self.create_button("Smart Start",Frame,6,0)
		#smartStart.configure(command = lambda: self.smart_start())
		#aikhong - add mqtt connect
		#mqtt = self.create_button("MQTT Setup and connect", buttonFrame,3,0)
		#mqtt.configure(command = lambda: self.mqtt_setupconnect())
		self.mqtt_setupconnect()
		self.handle_subscribe()
		#aik hong
		#self.binarySwitchButton = self.create_button("Toggle Switch",Frame,6,1)
		#self.binarySwitchButton.configure(command = lambda: self.binary_switch_action(1,255))
		#self.binarySwitchButton.grid_remove()
		self.client_init()
		self.node_list_action()
		self.create_thread()
		self.debugData.see(END)

#aikhong
	def do_action(self):
		global status, nodeid, value, type

		if(status == "binary"):
			#print("control node id " +str(nodeid) + " value " +str(value))
			self.binary_switch_action(nodeid, value)
			status = "none"
		if(status == "thermostat setpoint"):
			self.thermostat_setpoint(nodeid, value, type)
			status = "none"

	#need to get the descripito if value again if there are 2 devices having the same CC
	#the reason is that it will be overwritten by the last device.

	def get_descif(self, node):
		#self.debugData.insert(INSERT,"Poll list Device value: " +Znodeid[device])
		for interface in self.deviceInterfaceList:
			self.deviceDictionaryList[interface]['tempFoundDevice'] = 0
		r = self.zware.zw_api('zwnet_get_node_list')
		nodes = r.findall('./zwnet/zwnode')
		#print ("Node value = ", node)

		r2 = self.zware.zw_api('zwnode_get_ep_list', 'noded=' + nodes[int(node)].get('desc'))
		eps = r2.findall('./zwnode/zwep')
		for ep in range(len(eps)):
			epid = eps[ep].get('id')
			r3 = self.zware.zw_api('zwep_get_if_list', 'epd=' + eps[ep].get('desc'))
			intfs = r3.findall('./zwep/zwif')
			for intf in range(len(intfs)):
				if (intfs[intf].get('name') != "Unknown"):
					ifid = int(intfs[intf].get('id'))
					ifd = int(intfs[intf].get('desc'))
					#self.debugData.insert(INSERT,'ifd: ' + string(intfs[intf].get('desc')) +'\n' )
					for interface in self.deviceInterfaceList:
						if ifid == interface:
							self.deviceDictionaryList[interface]['ifdDevice'] = ifd
							self.deviceDictionaryList[interface]['tempFoundDevice'] = 1

	def get_descifofNode(self, ZwaveNodeID):

		#print("ZwaveNodeID:" +str(ZwaveNodeID))

		r = self.zware.zw_api('zwnet_get_node_list')
		nodes = r.findall('./zwnet/zwnode')
		for node in range(len(nodes)):
			nodeid = nodes[node].get('id')	#actual node ID in Z-Wave network
			#self.debugData.insert(INSERT,'node[' + str(node) + '] '+ "Z-Wave NodeID:"+ nodeid + "\n")	#mapping of Z-Wave node ID to Z-Ware ID
			if(ZwaveNodeID == int(nodeid)):
				descifnode = node

		#print("descif id:" +str(descifnode))
		return descifnode


	def get_node_list(self):
		#self.debugData.insert (INSERT,"get_node_list \n")
		devent = 0
		global Znodeid
		global sensor_event
		global binary_event
		global multilevel_sensor_event
		global message
		Znodeid = []

		r = self.zware.zw_api('zwnet_get_node_list')
		nodes = r.findall('./zwnet/zwnode')
		for node in range(len(nodes)):
			nodeid = nodes[node].get('id')	#actual node ID in Z-Wave network
			Znodeid.append(nodeid)
			self.debugData.insert(INSERT,'node[' + str(node) + '] '+ "id:"+ nodeid + "\n")	#mapping of Z-Wave node ID to Z-Ware ID

			r2 = self.zware.zw_api('zwnode_get_ep_list', 'noded=' + nodes[node].get('desc'))
			eps = r2.findall('./zwnode/zwep')
			for ep in range(len(eps)):
				device_name = eps[ep].get('name')
				self.debugData.insert(INSERT,'\tendpoint name: ' + device_name + "\n")	# no need to display name in mqtt as only Controller had name
				epid = eps[ep].get('id')	#endpoint ID

				r3 = self.zware.zw_api('zwep_get_if_list', 'epd=' + eps[ep].get('desc'))
				intfs = r3.findall('./zwep/zwif')
				self.debugData.insert (INSERT,"\t\tSupported Command Classes: \n")

				for intf in range(len(intfs)):
					if (intfs[intf].get('name') != "Unknown"):
						commandclass = intfs[intf].get('name')
						#aikhong
						self.debugData.insert(INSERT,'\t\t' + commandclass  + "\n")
						if commandclass == "COMMAND_CLASS_ALARM":
							device = "Alarm Device"
							data = {"device": device, "Node ID":nodeid}
							message = mqttc.json_encode(data) # encode oject to JSON
							topic = TOPIC_OF_PUBLISH + '/Type of Device/'
							send(topic)
							#self.mqttpublish(topic, device)
						if commandclass == "COMMAND_CLASS_SWITCH_BINARY":
							device = "Binary Switch"
							data = {"device": device, "Node ID":nodeid}
							message = mqttc.json_encode(data)   # encode oject to JSON
							topic = TOPIC_OF_PUBLISH + '/Type of Device/'
							send(topic)
							#self.mqttpublish(topic, device)
						if commandclass == "COMMAND_CLASS_SWITCH_MULTILEVEL":
							device = "Multilevel Switch"
							data = {"device": device, "Node ID":nodeid}
							message = mqttc.json_encode(data)   # encode oject to JSON
							topic = TOPIC_OF_PUBLISH + '/Type of Device/'
							send(topic)
						if commandclass == "COMMAND_CLASS_SENSOR_MULTILEVEL":
							device = "Multilevel Sensor"
							data = {"device": device, "Node ID":nodeid}
							message = mqttc.json_encode(data)   # encode oject to JSON
							topic = TOPIC_OF_PUBLISH + '/Type of Device/'
							send(topic)

							#self.mqttpublish(topic, device)
						#aikhong
						ifid = int(intfs[intf].get('id'))
						ifd = int(intfs[intf].get('desc'))
						for interface in self.deviceInterfaceList:
							if ifid == interface:
								self.deviceDictionaryList[interface]['ifdDevice'] = ifd
								self.deviceDictionaryList[interface]['tempFoundDevice'] = 1

		#creating a matrix - the size of each matrix table will be as big as the node list
		a = len(Znodeid)
		print("\nForming the table, with column = ", a)
		sensor_event = [[0] * a for i in range(a)]
		for i in range(a) :
			sensor_event[0][i] =0

		binary_event = [[0] * a for j in range(a)]
		for j in range(a) :
			binary_event[0][j] =0

		multilevel_sensor_event = [[0] * a for k in range(a)]
		for k in range(a) :
			multilevel_sensor_event[0][k] =0


#aikhong
	##
	#\addtogroup poll_network
	#@{
	#\section polling Network Polling
	#The client polls the network both automatically in the background as well as on user prompt with the "Node Details" button. On polling succesfully the client displays a list of nodes along with all available endpoints connected to them.
	#It also displays a list of all the Command Classes supported by each endpoint. This is achieved using:<br>1. The Client queries for available nodes.<br>2.
	#On succesfully retrieving the node list the client queries for available endpoints for each node.<br>3.
	#Subsequently for each endpoint it will query for the supporting command classes. Once all data has been retrieved it will either be
	#a:)Be displayed to the user if they had clicked on the "Node Details" button or
	#b:)Be used for further background polling of devices.
	#\section tracking Tracking Devices
	#The client will constantly be polling the network for tracking devices and their state values. In the present version this support is provided for Binary Switches, Binary Sensors and Multilevel Sensors. For example whenever a binary switch is added or removed from a network the client will display this information to the user. This is achieved using the polling web-apis mentioned above along with identifying the binary switch using it's interface id.
	#@}
	def poll_node_list(self,buttonPress):
		#self.debugData.insert (INSERT,"poll_node_list \n")
		poll = None	# clean up poll value
		node = 0;

		#self.debugData.insert(INSERT,"Poll list Device value: " +Znodeid[device])
		for interface in self.deviceInterfaceList:
			self.deviceDictionaryList[interface]['tempFoundDevice'] = 0
		r = self.zware.zw_api('zwnet_get_node_list')
		nodes = r.findall('./zwnet/zwnode')
		#print ("\nlength of Znodeid =", +len(Znodeid))

		for device in range(len(Znodeid)):
			#for node in range(len(nodes)):
			if node < len(Znodeid):
				r2 = self.zware.zw_api('zwnode_get_ep_list', 'noded=' + nodes[node].get('desc'))
				eps = r2.findall('./zwnode/zwep')
				for ep in range(len(eps)):
					epid = eps[ep].get('id')
					r3 = self.zware.zw_api('zwep_get_if_list', 'epd=' + eps[ep].get('desc'))
					intfs = r3.findall('./zwep/zwif')
					for intf in range(len(intfs)):
						if (intfs[intf].get('name') != "Unknown"):
							commandclass = intfs[intf].get('name')
							if commandclass == "COMMAND_CLASS_ALARM":
								#self.debugData.insert(INSERT,"CC Alarm for " + str(node) + '\n' )
								poll = "notification"
							elif commandclass == "COMMAND_CLASS_SENSOR_MULTILEVEL":
									poll = "sensor_multilevel"
							elif commandclass == "COMMAND_CLASS_SWITCH_BINARY":
								poll = "binary_switch"
							elif commandclass == "COMMAND_CLASS_SWITCH_MULTILEVEL":
								poll = "binary_switch"
							#else:
							#	poll ="Nothing"

						ifid = int(intfs[intf].get('id'))
						ifd = int(intfs[intf].get('desc'))
						#self.debugData.insert(INSERT,'ifd: ' + string(intfs[intf].get('desc')) +'\n' )
						for interface in self.deviceInterfaceList:
							if ifid == interface:
								self.deviceDictionaryList[interface]['ifdDevice'] = ifd
								self.deviceDictionaryList[interface]['tempFoundDevice'] = 1
			for interface in self.deviceInterfaceList:
				if self.deviceDictionaryList[interface]['tempFoundDevice'] != self.deviceDictionaryList[interface]['foundDevice']:
					self.deviceDictionaryList[interface]['previouslyFoundDevice'] = self.deviceDictionaryList[interface]['foundDevice']
				self.deviceDictionaryList[interface]['foundDevice'] = self.deviceDictionaryList[interface]['tempFoundDevice']

			if poll == "notification":
				 #self.debugData.insert(INSERT,"node value " +str(node) + '\n')
				 self.poll_notification_sensor(node);
			elif poll == "binary_switch":
				#self.debugData.insert(INSERT,"Poll_Binary Switch")
				self.poll_binary_switch(node);
			elif poll == "sensor_multilevel":
				#self.debugData.insert(INSERT,"poll_multilevel_sensor")
				self.poll_multilevel_sensor(node);
			#else:
				#self.debugData.insert(INSERT,"No Polling\n")

			node = node+1

	def node_list_action(self):
		#self.poll_node_list(True)	#aikhong --
		self.get_node_list()	#aikhong ++
		self.debugData.insert(INSERT,'Finished getting node details\n')
		self.debugData.see(END)

	##
	#\addtogroup binary_switch
	#@{
	#\section polling_switch Polling Binary Switch state
	#On polling for node list the client will also track device and their state values. This is applicable to Binary Switches in this version. Once a binary switch is found in the network the client will retrieve the switch's last known state from the server. Every time the binary switch's state changes it will send out a report to the server which will be stored as the last known state in the server.
	#\section toggle_switch Toggle Binary Switch
	#Whenever a binary switch is detected in the network the "Toggle Switch" button will be visible in the client. Note that this is possible when a)polling the network and detecting a binary switch or b)Including a binary switch using the client.<br> Once the button is visible the user can manually change the state of the binary switch by clicking on the button. For example if the switch is turned off and the user presses the button it will be turned on.
	#\section Stop Binary Switch tracking
	#Whenever a binary switch is removed from the network the client will inform this to the user. Once the switch is removed the "Toggle Switch" button will be no longer be visible in the client. The removal can happen either using the client's "Exclude Device" button or by removing the switch from the network manually by the user. In either case the information will be relayed to the user by the client.
	#@}
	def poll_binary_switch(self, node):
		global binary_event
		global message

		if self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['foundDevice'] == 1:
			self.zware.zwif_switch_api(self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['ifdDevice'], 1)
			v = int(self.zware.zwif_switch_api(self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['ifdDevice'], 3).get('state'))
			# aikhong - since we only poll when we found binary switch command, the below code is not needed
			# in addition, we aldo not contolling the switch using the button, but via MQTT, so the code on enable_disable_binary switch will be remove

			loc = Znodeid[node]	# the Z-Wave node ID

			#print("loc " +str(loc) + " node " +str(node))
			binary_event[0][node] = loc 	#map [0][x] to node id

			last_binary_value = binary_event[node-1][0]
			new_binary_value = v
			binary_event[node-1][0] = new_binary_value	#update the new device status

			#self.debugData.insert(INSERT,"Node for Polling in Binary Switch " +str(node) + '\n')

			if last_binary_value != new_binary_value:
				self.debugData.insert(INSERT,"Change in state\n")
				topic = TOPIC_OF_PUBLISH + '/' + 'state' + '/'
				data = {"device": "wallpluga", "value": new_binary_value }	#need to update device name as we goes along
				message = mqttc.json_encode(data)   # encode oject to JSON
				send(topic)
				#self.mqttpublish(topic, new_binary_value)
			#else:
			#	self.debugData.insert(INSERT,"No change in state\n")

			#remove the checking state - aikhong
			if False:
				if self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['previouslyFoundDevice'] == 0:
					self.debugData.insert(INSERT,"Polling: Switch found in network\n")
					self.enable_disable_binary_switch()
					self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['previouslyFoundDevice'] = 1
					if v == 255:
						self.debugData.insert(INSERT,"Polling: Switch is turned on\n")
					else:
						self.debugData.insert(INSERT,"Polling: Switch is turned off\n")
					self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['defaultState'] = v
				if self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['defaultState'] != v:
					if v == 255:
						self.debugData.insert(INSERT,"Polling: Switch has been turned on\n")
					else:
						self.debugData.insert(INSERT,"Polling: Switch has been turned off\n")
					self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['defaultState'] = v
			#remove till here
		#removing...
		#elif self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['previouslyFoundDevice'] == 1:
		#		self.debugData.insert(INSERT,"Polling: Switch removed from network\n")
		#		self.enable_disable_binary_switch()
		#		self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['previouslyFoundDevice'] = 0
		if self.runPollingThread:
			self.debugData.see(END)

	# need to define whether to turn it ON or OFF
	def binary_switch_action(self, node, value):
		# JSON format
		#{
  		#	"nodeid":"7",
  		#	"command" : "switch",
  		#	"value": "255"
		#}
		global binary_event
		global Znodeid
		timer = 0
		i = 0

		if self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['foundDevice'] == 0:
			self.debugData.insert(INSERT,"No switch is found in network\n")
		else:
			node = int(node)	# need to find out node id
			a = len(Znodeid)

			i = self.get_descifofNode(node)
			self.get_descif(i)

			if( int(value) == 255):
				ifd = self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['ifdDevice']
				self.zware.zwif_switch_api(ifd, 1)
				self.zware.zwif_switch_api(ifd, 4, "&value=1")
				timer = 0
				v = int(self.zware.zwif_switch_api(ifd, 2).get('state'))
				while (v == 0) and (timer < 10):
					v = int(self.zware.zwif_switch_api(ifd, 2).get('state'))
					time.sleep(2)
					timer = timer + 1
				self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['defaultState'] = v
				if v == 255:
					self.debugData.insert(INSERT,"Switch has been turned on\n")
					binary_event[i][0] = v			#update the new device status
				else:
					self.debugData.insert(INSERT,"Switch could not be turned on\n")
					binary_event[i][0] = 0			#update the new device status

			else:	#value is 0
				ifd = self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['ifdDevice']
				self.zware.zwif_switch_api(ifd, 1)
				self.zware.zwif_switch_api(ifd, 4, "&value=0")
				timer = 0
				v = int(self.zware.zwif_switch_api(ifd, 2).get('state'))
				while (v == 255) and (timer < 10):
					v = int(self.zware.zwif_switch_api(ifd, 2).get('state'))
					time.sleep(2)
					timer = timer + 1
				self.deviceDictionaryList[self.BINARYSWITCHINTERFACE]['defaultState'] = v
				if v == 0:
					self.debugData.insert(INSERT,"Switch has been turned off\n")
					binary_event[i][0] = v		#update the new device status
				else:
					self.debugData.insert(INSERT,"Switch could not be turned off\n")
					binary_event[i][0] = 255
		self.debugData.see(END)

	def thermostat_setpoint(self, node, value, type):

		#JSON format :
		#{
		#	"nodeid":"6", //node id of Z-Wave network"
  		#	"command" : "thermostat setpoint setting",
  		#	"value": "22",	//temperature in celsius
  		#	"type" : "cooling"	// or "heating"
		#}

		i = 0

		# do note that we are using MULTILEVELSENSORINTERFACE, because the Remotec had the multilevel_sensor too
		# a better way to do it is to use THERMOSTATSETPOINTINTERFACE
		if self.deviceDictionaryList[self.MULTILEVELSENSORINTERFACE]['foundDevice'] == 0:
			self.debugData.insert(INSERT,"No thermostat device is found in network\n")
		else:
			node = int(node)	# need to find out node id
			i = self.get_descifofNode(node)
			#print("value of i" +str(i))
			self.get_descif(i)

			if type == "heating" :
				setpoint = 1
			else:
				setpoint = 2

			cmd = "&type="+str(setpoint)+"&value="+str(value)+"&precision=1&unit=0"
			#print("\ncmd:" +cmd)
			ifd = self.deviceDictionaryList[self.THERMOSTATSETPOINTINTERFACE]['ifdDevice']
			self.zware.zwif_thermo_setpoint_api(ifd, 1)
			#self.zware.zwif_thermo_setpoint_api(ifd, 4, "&type=1&value=23&precision=1&unit=0")
			self.zware.zwif_thermo_setpoint_api(ifd, 4, cmd)

		self.debugData.see(END)


	def poll_binary_sensor(self):
		if self.deviceDictionaryList[self.BINARYSENSORINTERFACE]['foundDevice'] == 1:
			self.zware.zwif_bsensor_api(self.deviceDictionaryList[self.BINARYSENSORINTERFACE]['ifdDevice'], 1)
			r = self.zware.zwif_bsensor_api(self.deviceDictionaryList[self.BINARYSENSORINTERFACE]['ifdDevice'], 3)
			v = int(r.get('state'))
			t = r.get('type')
			binary_sensor_type = "Polling: Binary Sensor type:" + t + "\n"
			if self.deviceDictionaryList[self.BINARYSENSORINTERFACE]['previouslyFoundDevice'] == 0:
				self.debugData.insert(INSERT,"Polling: Binary Sensor found in network\n")
				self.deviceDictionaryList[self.BINARYSENSORINTERFACE]['previouslyFoundDevice'] = 1
				if v == 255:
					self.debugData.insert(INSERT,binary_sensor_type)
					self.debugData.insert(INSERT,"Polling: Binary Sensor has detected an event\n")
				else:
					self.debugData.insert(INSERT,binary_sensor_type)
					self.debugData.insert(INSERT,"Polling: Binary Sensor is idle\n")
				self.deviceDictionaryList[self.BINARYSENSORINTERFACE]['defaultState'] = v
			if v == 255:
				self.debugData.insert(INSERT,binary_sensor_type)
				self.debugData.insert(INSERT,"Polling: Binary Sensor has detected an event\n")
				self.deviceDictionaryList[self.BINARYSENSORINTERFACE]['defaultState'] = v
		elif self.deviceDictionaryList[self.BINARYSENSORINTERFACE]['previouslyFoundDevice'] == 1:
				self.debugData.insert(INSERT,"Polling: Binary Sensor removed from network\n")
				self.deviceDictionaryList[self.BINARYSENSORINTERFACE]['previouslyFoundDevice'] = 0
		if self.runPollingThread:
			self.debugData.see(END)

	#aikhong - add NOTIFICATIONINTERFACE
	##
	#\addtogroup notification
	#@{
	#\section polling_sensor Polling Notification Sensor State
	#On polling for node list the client will also track device and their state values. This is applicable to notification Sensors in this version.
	#Once a notification sensor is found in the network the client will retrieve the notification's last known state from the server.
	#Every time the notification sensor's state changes it will send out a report to the server which will be stored as the last known state in the server.
	#Additionally along with the value the client will also display the sensor type.
	#@}
	def poll_notification_sensor(self, node):
		#self.debugData.insert(INSERT,"PNS: " +string(node)+ '\n')	#debugging
		#print(node)
		global message

		if self.deviceDictionaryList[self.NOTIFICATIONINTERFACE]['foundDevice'] == 1:
			self.zware.zwif_notification_api(self.deviceDictionaryList[self.NOTIFICATIONINTERFACE]['ifdDevice'], 1)
			r = self.zware.zwif_notification_api(self.deviceDictionaryList[self.NOTIFICATIONINTERFACE]['ifdDevice'], 3)
			#aikhong
			if r == None:
				#print("Error in connecting to ZIPGW, try again in Web")
				#self.debugData.insert(INSERT,"Error in connecting to ZIPGW, try connecting again in Web Notification Sensor ")
				#self.debugData.insert(INSERT,"\nNo notification send out")
				r=0
			else:
				xml = ET.tostring(r, encoding='unicode')
				notification_device_data = "Polling: Notification Information:" + xml + "\n"
				#notification_device_data = "Polling: Notification data Type:" + a + "," + "Time Stamp:" + ts + "\n"

				sub = xml.find("ztype")
				sub1 = xml.find("event")
				#print("\Location of ztype", sub)
				#print("Value of ztype", xml[sub+7])

				ztype = int(xml[sub+7])
				if ztype == 7:
					#print("This is a motion sensor")
					a = 1	#no meaning, TBR
				else:
					print("Unknown sensor")

				#self.debugData.insert(INSERT,"Znodeid: " +string(node)+ '\n')	#debugging
				#find current state of PIR sensor, 0 = no motion, 8 = motion detected
				#print("Znode id" +str(node))
				loc = Znodeid[node]	# the Z-Wave node ID
				last_sensor_event = sensor_event[node-1][0]
				new_sensor_event = int(xml[sub1+7])
				sensor_event[node-1][0] = new_sensor_event	#update the sensor event

				if last_sensor_event != new_sensor_event:
					topic = TOPIC_OF_PUBLISH + '/' + 'event' + '/'
					data = {"device": "door", "value":new_sensor_event}
					message = mqttc.json_encode(data)   # encode oject to JSON
					send(topic)


		elif self.deviceDictionaryList[self.NOTIFICATIONINTERFACE]['previouslyFoundDevice'] == 1:
			self.debugData.insert(INSERT,"Polling: Notificaton Device removed from network\n")
			self.deviceDictionaryList[self.NOTIFICATIONINTERFACE]['previouslyFoundDevice'] = 0

		if self.runPollingThread:
			self.debugData.see(END)

		#aikhong add NOTIFICATIONINTERFACE

	##
	#\addtogroup multilevel_sensor
	#@{
	#\section polling_msensor Polling Multilevel Sensor Data
	#On polling for node list the client will also track device and their state values. This is applicable to Multilevel Sensors in this version.
	#Once a multilevel sensor is found in the network the client will retrieve the sensor's last known value from the server.
	#Every time the multilevel sensor's value changes it will send out a report to the server which will be stored as the last known value in the server.
	#Additionally along with the value the client will also display the sensor type, precision and unit.
	#@}
	def poll_multilevel_sensor(self, node):

		global message

		if self.deviceDictionaryList[self.MULTILEVELSENSORINTERFACE]['foundDevice'] == 1:
			self.zware.zwif_sensor_api(self.deviceDictionaryList[self.MULTILEVELSENSORINTERFACE]['ifdDevice'], 1)
			r = self.zware.zwif_sensor_api(self.deviceDictionaryList[self.MULTILEVELSENSORINTERFACE]['ifdDevice'], 3)
			if r == None:
				#print("Error in connecting to ZIPGW, try again in Web")
				self.debugData.insert(INSERT,"Error in connecting to ZIPGW- Multilevel, try connecting again in Web")
			else:
				v = r.get('value')
				t = r.get('type')
				if(t == "1"):
					device_type= "temperature sensor"
				else:
					device_type="Unknown"

				p = int(r.get('precision'))
				u = r.get('unit')
				multilevel_poll_value = "Polling: Multilevel Sensor Type:" + t + "," + "Value:" + v + "," + "Precision:" + str(p) + "," + "Unit:" + u + "\n"
				#self.debugData.insert(INSERT, multilevel_poll_value)

				loc = Znodeid[node]	# the Z-Wave node ID
				last_multilevel_sensor_event = multilevel_sensor_event[node-1][0]
				new_multilevel_sensor_event = round((float(v)),2)
				multilevel_sensor_event[node-1][0] = new_multilevel_sensor_event	#update the sensor event

				if last_multilevel_sensor_event != new_multilevel_sensor_event:
					topic = TOPIC_OF_PUBLISH + '/' + 'event' + '/'
					data = {"device":device_type  , "value":new_multilevel_sensor_event}
					message = mqttc.json_encode(data)   # encode oject to JSON
					send(topic)


			#if self.deviceDictionaryList[self.MULTILEVELSENSORINTERFACE]['previouslyFoundDevice'] == 0:
			#	self.debugData.insert(INSERT,"Polling: Multilevel Sensor found in network\n")
			#	self.deviceDictionaryList[self.MULTILEVELSENSORINTERFACE]['previouslyFoundDevice'] = 1
			#	self.debugData.insert(INSERT,multilevel_poll_value)
			#	self.deviceDictionaryList[self.MULTILEVELSENSORINTERFACE]['defaultState'] = v
			#if self.deviceDictionaryList[self.MULTILEVELSENSORINTERFACE]['defaultState'] != v:
			#	self.debugData.insert(INSERT,"Polling: Multilevel Sensor Updated\n")
			#	self.debugData.insert(INSERT,multilevel_poll_value)
			#	self.deviceDictionaryList[self.MULTILEVELSENSORINTERFACE]['defaultState'] = v
		elif self.deviceDictionaryList[self.MULTILEVELSENSORINTERFACE]['previouslyFoundDevice'] == 1:
				self.debugData.insert(INSERT,"Polling: Multilevel Sensor removed from network\n")
				self.deviceDictionaryList[self.MULTILEVELSENSORINTERFACE]['previouslyFoundDevice'] = 0
		if self.runPollingThread:
			self.debugData.see(END)

#mqtt code
#===========================================================================================================
	def mqtt_setupconnect(self):
		#mqttc = AWSIoTMQTTClient("Sensor")
		#Use the endpoint from the settings page in the IoT console
		#mqttc.configureEndpoint("data.iot.ap-southeast-1.amazonaws.com",8883)
		mqttc.configureEndpoint("a1b0zdpxwpwpyy-ats.iot.ap-southeast-1.amazonaws.com",8883)
		mqttc.configureCredentials("./rootCA.pem","./sensor.private.key","./sensor.cert.pem")
		mqttc.connect()
		print ("mqtt Connected")
		return

	#Function to encode a payload into JSON
	def json_encode(self, string):
		return json.dumps(string)

	#def mqttencode(self, string):
	#    mqttc.json_encode=self.json_encode

	#This sends our test message to the iot topic
	def mqttpublish(self, topic, message):
		if message == 0:
			print("make message 0 into real 0")
			message = "0"	# if message value = 0, when str, nothing will appear

		message = self.json_encode(message)
		#debugging
		Publish_Messsage = "Topic:" + str(topic) + "," + "Message:" + str(message) + "\n"
		self.debugData.insert(INSERT,Publish_Messsage)
		#debugging
		mqttc.publish(topic, message, 0)
		print ("Message Published")
		return

	def handle_subscribe(self):
		print("--------------------------------handle_subscribe")
		print("Subscribing to topic: " +str(TOPIC_OF_SUBSCRIBE))
		mqttc.subscribe(TOPIC_OF_SUBSCRIBE , 0, customCallback)
		time.sleep(2)
		return

	def mqtt_disconnect(self):
		mqttc.disconnect()
		print ("mqtt disconnect\n")
		return

#mqtt code
#===========================================================================================================

	#Background polling
	def poll_server(self):
		while self.runPollingThread:
			self.poll_node_list(False)
			self.do_action()
			time.sleep(2)

	#GUI Rendering and Code Cleaning
	def client_init(self):
		self.runPollingThread = True

	def create_thread(self):
		userThread = Thread(target=self.poll_server)
		userThread.daemon = True
		userThread.start()

	def create_window(self,windowName):
		userWindow = Toplevel()
		userWindow.title(windowName)
		return userWindow

	def create_frame(self,container):
		userFrame = Frame(container)
		userFrame.pack()
		return userFrame

	def clear_frame(self,frame):
		for widget in frame.winfo_children():
			widget.destroy()

	def disable_frame(self,frame):
		for widget in frame.winfo_children():
			widget.configure(state='disable')

	def enable_frame(self,frame):
		for widget in frame.winfo_children():
			widget.configure(state='active')

	def create_text(self,container,rowNumber,columnNumber):
		userText = Text(container)
		userText.grid(row=rowNumber,column=columnNumber,sticky=(N,S,E,W))
		return userText

	def create_scrollbar(self,container,rowNumber,columnNumber):
		userScrollBar = Scrollbar(container)
		userScrollBar.grid(row=rowNumber,column=columnNumber,sticky=(N,S,E,W))
		return userScrollBar

	def create_label(self,labelName,container,rowNumber,columnNumber):
		userLabel = Label(container, text=labelName)
		userLabel.grid(row=rowNumber,column=columnNumber,sticky=(N,S,E,W))
		return userLabel

	def create_radiobutton(self,buttonName,buttonVariable,buttonValue,container,rowNumber,columnNumber):
		Radiobutton(container,text=buttonName,variable=buttonVariable,value=buttonValue).grid(row=rowNumber,column=columnNumber,sticky=(N,S,E,W))

	def create_checkbox(self,checkboxName,checkboxVariable,container,rowNumber,columnNumber):
		userCheckBox = Checkbutton(container,text=checkboxName,variable=checkboxVariable)
		userCheckBox.grid(row=rowNumber,column=columnNumber,sticky=(N,S,E,W))
		return userCheckBox

	def create_drop_down_list(self,dropDownListVariable,container,listitem1,listitem2,listitem3,rowNumber,columnNumber):
		OptionMenu(container,dropDownListVariable,listitem1,listitem2,listitem3).grid(row=rowNumber,column=columnNumber,sticky=(N,S,E,W))

	def create_entry(self,container,rowNumber,columnNumber):
		userEntry = Entry(container)
		userEntry.grid(row=rowNumber,column=columnNumber,sticky=(N,S,E,W))
		return userEntry

	def create_button(self,buttonName,container,rowNumber,columnNumber):
		userButton = Button(container, text = buttonName)
		userButton.grid(row=rowNumber, column=columnNumber,sticky=(N,S,E,W))
		return userButton

	def close_window(self,Toplevel):
		Toplevel.destroy()
		self.runPollingThread = False

	def close_child_window_and_refocus_main_window(self,childWindow,mainWindow):
		childWindow.destroy()
		mainWindow.deiconify()

	def close_connection(self,Button,initialFrame,buttonFrame):
		Button['state'] = 'normal'
		self.enable_frame(initialFrame)
		self.clear_frame(buttonFrame)
		#disconnect mqtt - aikhong
		#mqtt_dc = self.create_button("Disconect mqtt",Frame,7,0)
		#mqtt_dc.configure(command =lambda: self.mqtt_disconnect())
		self.mqtt_disconnect()
		#aikhong
		self.debugData.delete('1.0', END)
		self.runPollingThread = False

#Application Entry point

def main():
	zware_client_window = Tk()
	zware_client_window.title("Z-Ware Sample Client")
	zware = zwareWebApi()
	zwareClient = zwareClientClass(zware)
	zwareClient.main_window(zware_client_window)
	zware_client_window.mainloop()

main()
