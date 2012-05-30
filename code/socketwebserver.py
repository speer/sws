#!/usr/bin/python

import socket
import os
from multiprocessing import Process, Queue

class SecureWebServer:

	def rootProcessHandler(self, queue, serversocket):
		serversocket.close();
		print 'root process created: UID:', os.getuid()
		while 1:
			msg = queue.get()
			print 'privileged process',os.getpid(),'got',msg
			#### do forking here

			queue.put("answer from root: "+msg)

	def clientProcessHandler(self, queue, connection, addr, serversocket):
		serversocket.close()
		print 'new client',addr
		# receive message
		request = connection.recv(1024)
		print 'unprivileged process',os.getpid(),'got:',request
		# forward message to root process
		queue.put(request)
		# wait for roots response
		response = queue.get()
		# return response to client
		connection.send(response)

	def __init__(self, listenerUid, listenerGid, host='', port=80):
		self.host = host
		self.port = port
		self.listenerUid = listenerUid
		self.listenerGid = listenerGid
		
		# create server socket and bind to port
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.bind((self.host, self.port))
		s.listen(5)
		
		# create queue for interprocess communication
		communicationQueue = Queue()
		
		# create root process which stays in background and forks child processes
		rootProcess = Process (target=self.rootProcessHandler,args=(communicationQueue,s))
		rootProcess.start()

		# remove root privilege from listener process
		os.setgid(self.listenerGid)
		os.setuid(self.listenerUid)

		print 'listener serves forever: UID:', os.getuid()

		# serve forever
		while 1:
			# blocks until new incoming connection
			conn, addr = s.accept()

			# create new client process for handling this connection
			clientHandlerProcess = Process (target=self.clientProcessHandler,args=(communicationQueue,conn,addr,s))
			clientHandlerProcess.start()

			# listener process does not need to keep open the client connection
			conn.close()


s = SecureWebServer(1000,1000)
