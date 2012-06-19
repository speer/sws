#!/usr/bin/python

import select
import socket
import os
from multiprocessing import Process
import subprocess
import sys

import httprequest

class UnprivilegedProcess:
	
	def __init__(self, connection):
		# initialize HTTP request
		request = httprequest.HttpRequest(connection)
		# receive data and parse
		request.receive()

		# check for validity of request
		if request.checkValidity():

			# request OK - process it
			request.process(False)

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

		self.socketList = [rootListener]

		while 1:
			try:
				readReady, writeReady, exceptReady = select.select(self.socketList, [], [])
			except:
				break;
			for readySocket in readReady:
				if readySocket == rootListener:
					conn, addr = rootListener.accept()
					self.socketList.append(conn)
				else:
					unprivilegedProcess = UnprivilegedProcess(readySocket)
					self.socketList.remove(readySocket)


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

		self.socketList = [self.listener]
		self.requests = []
		self.rootSockets = []

		# serve forever
		while 1:
			try:
				readReady, writeReady, exceptReady = select.select(self.socketList, [], [])
			except:
				break;
			for readySocket in readReady:
				if readySocket == self.listener:
					conn, addr = self.listener.accept()
					print 'new connection from',addr
					self.socketList.append(conn)
				elif readySocket in self.rootSockets:
					for request in self.requests:
						if request.rootSocket == readySocket:
							# wait for roots response
							responseMsg = ''
							data = 'init'
							while data != '':
								data = readySocket.recv(4096)
								responseMsg = responseMsg + data
							request.response.message = responseMsg

							# remove from socketlist
							self.socketList.remove(readySocket)
							self.rootSockets.remove(readySocket)
							self.socketList.remove(request.connection)
							self.requests.remove(request)
							# return response to client and close connection
							request.sendResponse()
							# close connection to root
							readySocket.close()
							break
				else:
					# initialize HTTP Request
					request = httprequest.HttpRequest(readySocket)
					# receive request data and parse it
					request.receive()
		
					# just forward request to root process if syntax is valid
					if request.checkValidity():
						# add request to list
						self.requests.append(request)
						# establish connection to root process
						rootSocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
						rootSocket.connect(self.unixSocketPath)
						# forward message to root process
						rootSocket.send(request.request.message)
						# append to socketlist
						self.rootSockets.append(rootSocket)
						self.socketList.append(rootSocket)
						request.rootSocket = rootSocket
					else:
						# error in request
						request.generateResponseMessage()
						# return response to client and close connection
						request.sendResponse()
						# remove client from socketlist
						self.socketList.remove(readySocket)

	def shutdown (self):
		self.listener.close()


port = 80
if len(sys.argv) > 1:
	port = int(sys.argv[1])

SecureWebServer(1000,1000,port)

