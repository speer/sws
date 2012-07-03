#!/usr/bin/python

import select
import socket
import os
from multiprocessing import Process
import subprocess
import sys
import cPickle

import httprequest_select as httprequest

class UnprivilegedProcess:
	
	def __init__(self, connection, rootSocket):
		# forked client process does not need a open root listening socket
		rootSocket.close()

		request = httprequest.HttpRequest(connection,True)

		# check for validity of request
		if request.checkValidity():

			# request OK - process it
			request.process()

		# send response object back and close connection
		request.sendResponse(True)
		connection.close()


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



class SecureWebServer:

	LISTEN_QUEUE_SIZE = 10

	def __init__(self, listenerUid, listenerGid, port=80, host='', unixSocketPath="/tmp/sws.peerweb.it"):
		self.host = host
		self.port = port
		self.listenerUid = listenerUid
		self.listenerGid = listenerGid
		self.unixSocketPath = unixSocketPath
		
		# create server socket and bind to port
		self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.listener.bind((self.host, self.port))
		self.listener.listen(SecureWebServer.LISTEN_QUEUE_SIZE)
		# disable blocking mode
		self.listener.setblocking(0)

		# create root process which stays in background and forks child processes
		rootProcess = Process (target=PrivilegedProcess,args=(self,))
		rootProcess.start()

		# remove root privilege from listener process
		os.setgid(self.listenerGid)
		os.setuid(self.listenerUid)

		epoll = select.epoll()
		epoll.register(self.listener.fileno(), select.EPOLLIN)

		try:
			requests = {}
			rootRequests = {}

			# serve forever
			while 1:
				events = epoll.poll(1)
				for fileno, event in events:
					if fileno == self.listener.fileno():
						conn, addr = self.listener.accept()
						conn.setblocking(0)
						print 'new connection from',addr
						epoll.register(conn.fileno(), select.EPOLLIN)
						requests[conn.fileno()] = httprequest.HttpRequest(conn)	


					elif event & select.EPOLLIN:
						if fileno in rootRequests:
							print 'pollin from root'

							msg = rootRequests[fileno][0].recv(httprequest.HttpRequest.SOCKET_BUF_SIZE)
							rootRequests[fileno][3] = rootRequests[fileno][3] + msg
							if msg == '':
								request = requests[rootRequests[fileno][1]]
								wrapper = cPickle.loads(rootRequests[fileno][3])
								request.response = wrapper.response
								request.request = wrapper.request

								# Check if Location flag is set in CGI response
								if request.checkReprocess():

									# establish connection to root process
									rootConn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
									rootConn.connect(self.unixSocketPath)
									rootConn.setblocking(0)

									epoll.register(rootConn, select.EPOLLOUT)
	
									# forward request to root process, reinitialize response object
									data = cPickle.dumps(httprequest.RequestResponseWrapper(request.request,httprequest.Response()))
									data = str(len(data))+';'+data
									rootRequests[rootConn.fileno()] = [rootConn,rootRequests[fileno][1],data,'']	
								else:
									request.generateResponseMessage()

									# register client connection for poll out
									epoll.register(rootRequests[fileno][1],select.EPOLLOUT)

								# close connection to root
								epoll.modify(fileno, 0)
								rootRequests[fileno][0].shutdown(socket.SHUT_RDWR)
	
						else:
							print 'pollin from client'
							# ready to receive request data from client
							request = requests[fileno]

							if request.receiveRequest():
								# request fully received

								# just forward request to root process if syntax is valid
								if request.checkValidity():

									# establish connection to root process
									rootConn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
									rootConn.connect(self.unixSocketPath)
									rootConn.setblocking(0)

									epoll.register(rootConn, select.EPOLLOUT)

									# pickle request
									data = cPickle.dumps(httprequest.RequestResponseWrapper(request.request,httprequest.Response()))
									data = str(len(data))+';'+data
									rootRequests[rootConn.fileno()] = [rootConn,fileno,data,'']

									epoll.unregister(fileno)
								else:
									# error in request
									request.generateResponseMessage()
									epoll.modify(fileno, select.EPOLLOUT)


					elif event & select.EPOLLOUT:

						if fileno in rootRequests:
							print 'pollout to root'

							# send to root process
							byteswritten = rootRequests[fileno][0].send(rootRequests[fileno][2])
							rootRequests[fileno][2] = rootRequests[fileno][2][byteswritten:]

							if len (rootRequests[fileno][2]) == 0:
								# all data sent to root
								epoll.modify(fileno, select.EPOLLIN)

						else:
							print 'pollout to client'
							# ready to send response data to client
							request = requests[fileno]

							if request.sendResponse():
								# response fully sent
								epoll.modify(fileno, 0)
								try:
									request.connection.shutdown(socket.SHUT_RDWR)
								except socket.error:
									pass

					elif event and select.EPOLLHUP:

						epoll.unregister(fileno)

						if fileno in rootRequests:
							rootRequests[fileno][0].close()
							del rootRequests[fileno]
						else:
							requests[fileno].connection.close()	
							del requests[fileno]

		finally:
			epoll.unregister(self.listener.fileno())
			epoll.close()
			self.listener.close()
	

port = 80
if len(sys.argv) > 1:
	port = int(sys.argv[1])

SecureWebServer(1000,1000,port)

