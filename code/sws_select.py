#!/usr/bin/python

import select
import socket
import os
from multiprocessing import Process
import subprocess
import sys
import cPickle
import re
import time


import httprequest_select as httprequest

class UnprivilegedProcess:
	
	def __init__(self, connection, rootSocket):
		# forked client process does not need a open root listening socket
		rootSocket.close()

		request = httprequest.HttpRequest(connection)

		data = 'init'
		msg = ''
		msgLength = -1
		while data != '':
                        data = connection.recv(httprequest.HttpRequest.SOCKET_BUF_SIZE)
                        msg = msg + data
			m = re.match(r'(\d+);(.*)',msg,re.DOTALL)
			if m != None and msgLength == -1:
				msgLength = int(m.group(1))
				msg = m.group(2)
			if msgLength <= len(msg):
				# all data received
				break

		# retrieve request and unpickle it
		request.unpickle(msg)

		# check for validity of request
		if request.checkValidity():

			# request OK - process it, send response to listener and close connection at the end
			request.process()


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
		rootListener.listen(SecureWebServer.LISTEN_QUEUE_SIZE)

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
						# 1. new incoming connection
						conn, addr = self.listener.accept()
						conn.setblocking(0)
						print 'new connection from',addr
						epoll.register(conn.fileno(), select.EPOLLIN)
						# create new request and store it in list
						request = httprequest.HttpRequest(conn)
						request.determineHostVars()
						requests[conn.fileno()] = request

					elif event & select.EPOLLIN:
						if fileno in rootRequests:
							msg = rootRequests[fileno][0].recv(httprequest.HttpRequest.SOCKET_BUF_SIZE)
							rootRequests[fileno][3] = rootRequests[fileno][3] + msg
							m = re.match(r'(\d+);(.*)',rootRequests[fileno][3],re.DOTALL)
							if m != None:
								msgLength = int(m.group(1))
								msg = m.group(2)
								if msgLength <= len(msg):
									# message fully received
									rootRequests[fileno][3] = msg[msgLength:]
									msg = msg[:msgLength]

									# 4. receive everything thats currently available from root
									request = requests[rootRequests[fileno][1]]
									wrapper = cPickle.loads(msg)
									# overwrite request and reponse objects just before the flush
									if not wrapper.response.flushed:
										request.response = wrapper.response
										request.request = wrapper.request
									else:
										# later just append message and update connectionclose
										request.response.message = request.response.message + wrapper.response.message
										request.response.connectionClose = wrapper.response.connectionClose

									# Check if Location flag is set in CGI response
									if request.checkReprocess():
	
										# establish connection to root process
										rootConn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
										rootConn.connect(self.unixSocketPath)
										rootConn.setblocking(0)
	
										epoll.register(rootConn, select.EPOLLOUT)
	
										rootRequests[rootConn.fileno()] = [rootConn,rootRequests[fileno][1],request.pickle(True),'']

									else:
										# register client connection for poll out, since data is available
										try:
											epoll.register(rootRequests[fileno][1],select.EPOLLOUT)
										except:
											pass

									if request.response.connectionClose:
										# close connection to root
										epoll.modify(fileno, 0)
										rootRequests[fileno][0].shutdown(socket.SHUT_RDWR)
	
						else:
							# 2. ready to receive request data from client
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

									# store request information in rootRequests array (connection to Root, connection to Client, Request, Response)
									rootRequests[rootConn.fileno()] = [rootConn,fileno,request.pickle(True),'']
									
									# unregister client, since no data to send to client is available jet
									epoll.unregister(fileno)
								else:
									# error in request, modify to send error data to client
									epoll.modify(fileno, select.EPOLLOUT)


					elif event & select.EPOLLOUT:

						if fileno in rootRequests:
							# 3. send to root process
							byteswritten = rootRequests[fileno][0].send(rootRequests[fileno][2])
							rootRequests[fileno][2] = rootRequests[fileno][2][byteswritten:]

							if len (rootRequests[fileno][2]) == 0:
								# all data sent to root, modify to read response from root
								epoll.modify(fileno, select.EPOLLIN)

						else:
							# 5. ready to send response data to client
							request = requests[fileno]
							if request.flushResponseToClient():
								# all currently available data flushed to client
								if request.response.connectionClose:
									# connection to root closed, so no more data
									epoll.modify(fileno, 0)
									try:
										request.connection.shutdown(socket.SHUT_RDWR)
									except socket.error:
										pass
								else:
									# there is more data that root has to send
									epoll.unregister(fileno)

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

