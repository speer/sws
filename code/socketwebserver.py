#!/usr/bin/python

import socket
import os
from multiprocessing import Process

class SecureWebServer:

	def privilegedClientProcessHandler(self, connection, addr, rootSocket):
		# forked client process does not need a open root listening socket
		rootSocket.close();
		# receive data from client
		request = connection.recv(4096);

		print 'privileged process',os.getpid(),'got:',request
		# parse HTTP request here
		# detect owner of resource
		# make process unprivileged
		# access resource, etc.

		# send response back
		connection.send('response: '+request)
		# close connection to client
		connection.close()



	def rootProcessHandler(self, serversocket):
		# forked root process does not need a open server/listening socket
		serversocket.close();
		print 'root process created: UID:', os.getuid()

		# create UNIX socket for communication with client processes
		rootListener = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
		try:
			# remove eventual old socket
			os.remove(self.unixSocketPath)
		except OSError:
			pass
		rootListener.bind(self.unixSocketPath)
		# an unprivileged process has to have access to the socket
		os.chown(self.unixSocketPath,self.listenerUid,self.listenerGid)
		rootListener.listen(3)

		while 1:
			conn, addr = rootListener.accept()
			privilegedClientProcess = Process (target=self.privilegedClientProcessHandler,args=(conn,addr,rootListener,))
			privilegedClientProcess.start()
			conn.close()

	def clientProcessHandler(self, connection, addr, serversocket):
		# forked client process does not need a open server/listening socket
		serversocket.close()
		print 'new client',addr
		# receive message
		request = connection.recv(4096)
		print 'unprivileged process',os.getpid(),'got:',request

		# establish connection to root process
		rootSocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		rootSocket.connect(self.unixSocketPath)
		# forward message to root process
		rootSocket.send(request)
		# wait for roots response
		response = rootSocket.recv(4096)
		# close connection to root
		rootSocket.close()
		# return response to client
		connection.send(response)
		# close connection
		connection.close()

	def __init__(self, listenerUid, listenerGid, port=80, host='', unixSocketPath="/tmp/sws.peerweb.it"):
		self.host = host
		self.port = port
		self.listenerUid = listenerUid
		self.listenerGid = listenerGid
		self.unixSocketPath = unixSocketPath
		
		# create server socket and bind to port
		listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		listener.bind((self.host, self.port))
		listener.listen(5)
		
		# create root process which stays in background and forks child processes
		rootProcess = Process (target=self.rootProcessHandler,args=(listener,))
		rootProcess.start()

		# remove root privilege from listener process
		os.setgid(self.listenerGid)
		os.setuid(self.listenerUid)

		print 'listener serves forever: UID:', os.getuid()

		# serve forever
		while 1:
			# blocks until new incoming connection
			conn, addr = listener.accept()

			# create new client process for handling this connection
			clientHandlerProcess = Process (target=self.clientProcessHandler,args=(conn,addr,listener,))
			clientHandlerProcess.start()

			# listener process does not need to keep open the client connection
			conn.close()


s = SecureWebServer(1000,1000)
