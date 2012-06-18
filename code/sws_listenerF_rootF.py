#!/usr/bin/python

import socket
import os
from multiprocessing import Process
import subprocess
import sys

import httprequest

class UnprivilegedProcess:
	
	def __init__(self, connection, rootSocket):
		# forked client process does not need a open root listening socket
		rootSocket.close()

		# initialize HTTP request
		request = httprequest.HttpRequest(connection)
		# receive data and parse
		request.receive()

		# check for validity of request
		if request.checkValidity():
			# request OK - process it
			requestProcessor = httprequest.RequestProcessor(request)

			# remove root privilege from process, access ressource, etc.
			requestProcessor.processRequest()

		# generate response message
		request.generateResponseMessage()
		# send response back and close connection
		request.sendResponse()


class PrivilegedProcess:

	def __init__ (self, webserver):
		# forked root process does not need a open server/listening socket
		webserver.listener.close()

		# create UNIX socket for communication with client processes
		rootListener = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
		try:
			# remove eventual old socket
			os.remove(webserver.unixSocketPath)
		except OSError:
			pass
		rootListener.bind(webserver.unixSocketPath)
		# an unprivileged process has to have access to the socket
		os.chown(webserver.unixSocketPath,webserver.listenerUid,webserver.listenerGid)
		rootListener.listen(3)

		while 1:
			conn, addr = rootListener.accept()
			unprivilegedProcess = Process (target=UnprivilegedProcess,args=(conn,rootListener,))
			unprivilegedProcess.start()
			conn.close()


class ClientProcess:

	def __init__(self, webserver, connection, addr):
		# forked client process does not need a open server/listening socket
		webserver.listener.close()
		print 'new client',addr
		
		# initialize HTTP Request
		request = httprequest.HttpRequest(connection)
		# receive request data and parse it
		request.receive()
		
		# just forward request to root process if syntax is valid
		if request.checkValidity():
			# establish connection to root process
			rootSocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			rootSocket.connect(webserver.unixSocketPath)
			# forward message to root process
			rootSocket.send(request.requestMessage)
			# wait for roots response
			responseMsg = ''
			data = 'init'
			while data != '':
				data = rootSocket.recv(4096)
				responseMsg = responseMsg + data
			request.responseMessage = responseMsg
			# close connection to root
			rootSocket.close()
		else:
			# error in request
			request.generateResponseMessage()

		# return response to client and close connection
		request.sendResponse()


class SecureWebServer:

	def __init__(self, listenerUid, listenerGid, port=80, host='', unixSocketPath="/tmp/sws.peerweb.it"):
		self.host = host
		self.port = port
		self.listenerUid = listenerUid
		self.listenerGid = listenerGid
		self.unixSocketPath = unixSocketPath
		
		# create server socket and bind to port
		self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.listener.bind((self.host, self.port))
		self.listener.listen(5)

		# create root process which stays in background and forks child processes
		rootProcess = Process (target=PrivilegedProcess,args=(self,))
		rootProcess.start()

		# remove root privilege from listener process
		os.setgid(self.listenerGid)
		os.setuid(self.listenerUid)

		# serve forever
		while 1:
			# blocks until new incoming connection
			conn, addr = self.listener.accept()

			# create new client process for handling this connection
			clientHandlerProcess = Process (target=ClientProcess,args=(self,conn,addr,))
			clientHandlerProcess.start()

			# listener process does not need to keep open the client connection
			conn.close()


	def shutdown (self):
		self.listener.close()


port = 80
if len(sys.argv) > 1:
	port = int(sys.argv[1])

SecureWebServer(1000,1000,port)

