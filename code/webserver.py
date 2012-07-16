import select
import socket
import os
from multiprocessing import Process, Pipe
import subprocess
import sys
import cPickle
import re
import signal
import logging

import httprequest
import config
from daemon import Daemon

# This class handles an unprivileged process, that raised out of the fork of the root process
# It receives the HttpRequest object from the Listener Process
# Afterwards it processes the request
class UnprivilegedProcess:
	
	def __init__(self, connection, rootSocket, config):
		# forked client process does not need a open root listening socket
		rootSocket.close()

		# initialize new Request object
		request = httprequest.HttpRequest(connection,config)

		# receive Request from listener process
		request.receiveRequestFromListener()

		# process request, send response back to listener and close connection at the end
		request.process()


# This class represents the privileged root process, that listens on a UNIX socket and accepts new connections from the listener process
# it creates a new unprivileged process for each connection
class PrivilegedProcess:

	def __init__ (self, webserver):
		# forked root process does not need a open server/listening socket
		webserver.listener.close()

		# create UNIX socket for communication with client processes
		rootListener = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
		try:
			# remove eventual old socket
			os.remove(webserver.config.configurations['communicationsocketfile'])
		except OSError:
			pass
		rootListener.bind(webserver.config.configurations['communicationsocketfile'])
		# the listener process has to have access to the unix socket, therefore grant privileges to listener
		os.chown(webserver.config.configurations['communicationsocketfile'],webserver.config.configurations['user'],webserver.config.configurations['group'])
		rootListener.listen(webserver.config.configurations['listenqueuesize'])

		# create an event poller in order to be able to react on new connections and on termination events from the listener
		epoll = select.epoll()
		epoll.register(rootListener.fileno(), select.EPOLLIN)
		epoll.register(webserver.rootPipe.fileno(), select.EPOLLIN)

		while 1:
			# check for filedescriptors
			events = epoll.poll(1)
			for fileno, event in events:
				if fileno == rootListener.fileno():
					# new connection from listener process
					conn, addr = rootListener.accept()
					# for each connection a new unprivileged process is created
					unprivilegedProcess = Process (target=UnprivilegedProcess,args=(conn,rootListener,webserver.config))
					unprivilegedProcess.start()
					conn.close()
				else:
					# listener process terminated, terminate also privileged process
					if webserver.rootPipe.recv() == 'terminate':
						try:
							os.remove(webserver.config.configurations['communicationsocketfile'])
						except:
							pass
						sys.exit(0)


# This class creates the main architecture of the server
# It basically represents the Listener Process, which handles new incoming connections, manages communication between processes and clients
# Makes use of the select system call, i.e. epoll, to efficiently handle many connections simultaneously
class SecureWebServer (Daemon):

	# initialize the server, i.e. get configuration and try to listen at port
	def initialize(self, configuration_path):
		# parse config files
		self.config = config.SwsConfiguration(configuration_path)
		success, message = self.config.parseFile()
		if not success:	
			# log error message
			logging.getLogger('sws').error(message)
			return message

		self.rootProcess = None
	
		# create server socket and bind to port
		try:
			self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			self.listener.bind((self.config.configurations['host'], self.config.configurations['listen']))
			self.listener.listen(self.config.configurations['listenqueuesize'])
			# disable blocking mode of the listener socket
			self.listener.setblocking(0)
		except:
			logging.getLogger('sws').error('Could not bind server to port %s' % str(self.config.configurations['listen']))
			return 'Could not bind server to port ' + str(self.config.configurations['listen'])

		return None

	# start the server
	def run(self):	
		# register a pipe between root and listener for communication of process termination events
		self.listenerPipe, self.rootPipe = Pipe()
		signal.signal(signal.SIGTERM, self.shutdown)

		# create root process which stays in background and forks child processes
		self.rootProcess = Process (target=PrivilegedProcess,args=(self,))
		self.rootProcess.start()

		# remove root privilege from listener process
		os.setgid(self.config.configurations['group'])
		os.setuid(self.config.configurations['user'])

		# create an event poller in order to be able to handle simultaneous connections
		self.epoll = select.epoll()
		self.epoll.register(self.listener.fileno(), select.EPOLLIN)

		try:
			# contains HttpRequest objects for every client 
			# keys are the filenos - file descriptors - of the connections to the clients
			requests = {}

			# contains arrays for every connection to the unprivileged process
			# 1: fileno of connection to Root, 
			# 2: fileno of connection to Client, 
			# 3: pickled RequestResponseWrapper Object received from/sent to the unprivileged Process
			# keys are the filedescriptors for the communication with the unprivileged process
			rootRequests = {}

			# serve forever
			while 1:
				# check for filedescriptors that are readable or writable
				try:
					self.events = self.epoll.poll(1)
				except:
					# signal sigterm arrived
					break
				for fileno, event in self.events:
					if fileno == self.listener.fileno():
						# 1. new incoming connection
						conn, addr = self.listener.accept()
						conn.setblocking(0)
						#print 'new connection from',addr
						self.epoll.register(conn.fileno(), select.EPOLLIN)
						#print '1. register request:',conn.fileno()

						# create new request and store it in list
						request = httprequest.HttpRequest(conn,self.config)
						# determines some environment variables (IP address, hostname, etc.)
						request.determineHostVars()
						requests[conn.fileno()] = request

					elif event & select.EPOLLIN:
						# fileno is readable

						if fileno in rootRequests:
							# fileno is a filedescriptor for communication with the unprivileged process

							# check whether connection to client was shut down
							if not rootRequests[fileno][1] in requests:
								self.epoll.modify(fileno, 0)
								#print 'shutdown connection to root:',fileno
								rootRequests[fileno][0].shutdown(socket.SHUT_RDWR)
								break

							# receive part of the pickled message from the unprivileged process
							msg = rootRequests[fileno][0].recv(self.config.configurations['socketbuffersize'])
							rootRequests[fileno][2] = rootRequests[fileno][2] + msg
							m = re.match(r'(\d+);(.*)',rootRequests[fileno][2],re.DOTALL)
							if m != None:
								msgLength = int(m.group(1))
								msg = m.group(2)
								if msgLength <= len(msg):
									# 4. response object fully received
									rootRequests[fileno][2] = msg[msgLength:]
									msg = msg[:msgLength]

									request = requests[rootRequests[fileno][1]]
									wrapper = cPickle.loads(msg)
									# The first flush contains the whole header and a part of the body
									if not wrapper.response.flushed:
										request.response = wrapper.response
										request.request = wrapper.request
									else:
										# later just append message and update connectionclose
										request.response.message = request.response.message + wrapper.response.message
										request.response.connectionClose = wrapper.response.connectionClose

									# Check if Location flag is set in CGI response (local redirect)
									if request.checkReprocess():
	
										# establish connection to root process
										rootConn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
										rootConn.connect(self.config.configurations['communicationsocketfile'])
										rootConn.setblocking(0)
										#print '4. register new root connection:',rootConn.fileno()
										self.epoll.register(rootConn, select.EPOLLOUT)

										# update rootRequest array with new request data
										rootRequests[rootConn.fileno()] = [rootConn,rootRequests[fileno][1],request.pickle(True)]

									else:
										# register client connection for poll out, since data is available
										try:
											#print '4. register client for pollout:',rootRequests[fileno][1]
											self.epoll.register(rootRequests[fileno][1],select.EPOLLOUT)
										except:
											pass

									if request.response.connectionClose:
										# close connection to unprivileged process
										self.epoll.modify(fileno, 0)
										#print '5. shutdown connection to root:',fileno
										rootRequests[fileno][0].shutdown(socket.SHUT_RDWR)
	
						else:
							# 2. ready to receive request data from client
							request = requests[fileno]

							if request.receiveRequestFromClient():
								# request fully received

								# just forward request to root process if syntax is valid
								if request.checkValidity():

									# establish connection to root process
									rootConn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
									rootConn.connect(self.config.configurations['communicationsocketfile'])
									rootConn.setblocking(0)
									#print '2. register rootRequest:',rootConn.fileno(),' unregister request:',fileno

									self.epoll.register(rootConn, select.EPOLLOUT)

									# store request information in rootRequests array
									rootRequests[rootConn.fileno()] = [rootConn,fileno,request.pickle(True)]
									
									# unregister client, since no data to send to client is available jet
									self.epoll.unregister(fileno)

								else:
									# syntax error in request, modify epoll fileno to send error data to client
									self.epoll.modify(fileno, select.EPOLLOUT)

					elif event & select.EPOLLOUT:
						# fileno is writable

						if fileno in rootRequests:
							# 3. forward request to root process
							byteswritten = rootRequests[fileno][0].send(rootRequests[fileno][2])
							rootRequests[fileno][2] = rootRequests[fileno][2][byteswritten:]

							if len (rootRequests[fileno][2]) == 0:
								#print '3. data sent to root:',fileno
								# all data sent to root, modify to read response from root
								self.epoll.modify(fileno, select.EPOLLIN)

						else:
							# 5. ready to send response data to client
							request = requests[fileno]
							if request.flushResponseToClient():
								# all currently available data flushed to client
								if request.response.connectionClose:
									# connection to root closed, so no more data
									self.epoll.modify(fileno, 0)
									try:
										#print '6. shutdown connection to client:',fileno
										request.connection.shutdown(socket.SHUT_RDWR)
									except socket.error:
										pass
								else:
									# there is more data that root has to send
									self.epoll.unregister(fileno)
									#print '4.1 unregister client connection:',fileno

					elif event and select.EPOLLHUP:
						# fileno hung up or shutdown requested
						try:
							self.epoll.unregister(fileno)

							if fileno in rootRequests:
								#print '7. unregister/close rootRequest:',fileno
								rootRequests[fileno][0].close()
								del rootRequests[fileno]
							else:
								#print '7. unregister/close requests:',fileno
								requests[fileno].connection.close()
								del requests[fileno]
						except socket.error:
							pass

		finally:
			self.epoll.unregister(self.listener.fileno())
			self.epoll.close()
			self.listener.close()

	# root process must terminate when child terminates
	def shutdown(self,signal,frame):
		try:
			self.listenerPipe.send('terminate')
			self.listenerPipe.close()
		except:
			pass

