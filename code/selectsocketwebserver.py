#!/usr/bin/python

import select
import socket
import os
from os import path, sep, stat
from multiprocessing import Process
import subprocess
import re
import signal
import sys

# what should happen if a file is owned by root? what if a cgi script? -> if script: either error or nobody user
# don't always fork root process -> just if request headers have no content-length and if requested ressource is no cgi script and not a large file
# test HTTP parser with many browser (ie, ff, opera, chrome, safari, lynx, wget)

class RequestProcessor:

	def __init__(self, request):
		self.request = request
		self.documentroot = '/home/stefan/sws/docs'
		self.cgiroot = 'cgi-bin'
		self.resource = path.abspath(self.documentroot + sep + request.path)

	def processRequest (self):
		# check if resource is inside the documentroot (jail)
		if self.resource.startswith(self.documentroot):
			# check if resource is a valid file
			if os.path.isfile(self.resource):
				try:
					# check owner of the file
					st = os.stat(self.resource)
					# remove privileges
					os.setgid(st.st_gid)
					os.setuid(st.st_uid)
					# check if resource is a cgi script
					if self.resource.startswith(self.documentroot + sep + self.cgiroot):
						self.request.document = self.executeCGI()
					else:
						self.request.document = self.getFileContent()

					# temporary assume html content type
					self.request.responseHeaders['Content-Type'] = 'text/html'

				except:					
					self.request.setResponseError(500,'Internal Server Error','500: Internal Server Error')
			else:
				self.request.setResponseError(404,'File Not Found','404: The file could not be found')
		else:
			self.request.setResponseError(403,'Forbidden','403: Forbidden')
		

	def getFileContent(self):
		print 'resource retrieval by:',os.getuid()
		f = open(self.resource)
		return f.read()

	def executeCGI(self):
		print 'cgi execution by:',os.getuid()
        	if os.access(self.resource, os.X_OK):
                	p = subprocess.Popen([self.resource],stdout=subprocess.PIPE)
			return p.communicate()[0]
		else:
			raise IOError


class HttpRequest:

	def receive(self):
		data = ''
		msg = ''
                # get request line and all header fields
		while not msg.endswith('\r\n\r\n'):
			data = self.connection.recv(4096)
			msg = msg + data
		
		msg = msg.lstrip()
		lines = msg.split('\r\n')
		first = True
		for line in lines:
			line = line.strip()
			line = re.sub('\s{2,}', ' ', line)
			if first:
				# request line
				words = line.split(' ')
				if len(words) != 3:
					self.setResponseError(400,'Bad Request','Status 400 - Bad Request Line')
					return
				if words[0].upper() not in ['GET','POST','HEAD']:
					self.setResponseError(400,'Bad Request','Status 400 - Command not supported')
					return
				if words[2].upper() not in ['HTTP/1.0','HTTP/1.1']:
					self.setResponseError(400,'Bad Request','Status 400 - Version not supported')
					return
				self.command = words[0].upper()
				self.path = words[1]
				self.protocolVersion = words[2].upper()
				first = False
			else:
				if (line == ''):
					break
				# header line
				pos = line.find(':')
				if pos <= 0 or pos >= len(line)-1:
					self.setResponseError(400,'Bad Request','Status 400 - Bad Header')
					return
				key = line[0:pos].strip()
				value = line[pos+1:len(line)].strip()
				self.headers[key] = value
	
		self.statusCode = 200
		self.statusMessage = 'OK'
		self.document = ''
		self.requestMessage = msg

	def setResponseError(self, errorCode, errorMessage, errorDocument):
		self.statusCode = errorCode
		self.statusMessage = errorMessage
		self.document = errorDocument
		self.responseHeaders['Content-Type'] = 'text/html'

        def __init__ (self, connection):
		# request fields
		self.connection = connection
		self.command = None
		self.path = None
		self.protocolVersion = 'HTTP/1.1'
		self.headers = {}
		self.requestMessage = ''
		# response fields
		self.responseMessage = ''
		self.statusCode = None
		self.statusMessage = None
		self.document = None
		self.responseHeaders = {}
	
	def generateResponseMessage(self):
		m = self.protocolVersion+' '+str(self.statusCode)+' '+self.statusMessage+'\r\n'
		# add headers
		for hKey in self.responseHeaders.keys():
			m = m + hKey + ':' + self.responseHeaders[hKey]+'\r\n'
		self.responseMessage = m+'\r\n'+self.document

	def checkValidity(self):
		if self.statusCode == 200:
			return True
		return False

	def sendResponse(self):
		self.connection.send(self.responseMessage)
		self.connection.close()


class UnprivilegedProcess:
	
	def __init__(self, connection, rootSocket):
		# forked client process does not need a open root listening socket
		rootSocket.close()

		# initialize HTTP request
		request = HttpRequest(connection)
		# receive data and parse
		request.receive()

		# check for validity of request
		if request.checkValidity():
			# request OK - process it
			requestProcessor = RequestProcessor(request)

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
		print 'privileged process created: UID:', os.getuid()

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

	def clientProcessHandler(self, connection):
		print 'client communicating to server'
		# initialize HTTP Request
		request = HttpRequest(connection)
		# receive request data and parse it
		request.receive()
		
		print 'unprivileged process received request - pid:',os.getpid()

		# just forward request to root process if syntax is valid
		if request.checkValidity():
			print 'valid request forwarded to root'
			# establish connection to root process
			rootSocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			rootSocket.connect(self.unixSocketPath)
			# forward message to root process
			rootSocket.send(request.requestMessage)
			# wait for roots response
			request.responseMessage = rootSocket.recv(4096)
			# close connection to root
			rootSocket.close()
		else:
			print 'invalid request'
			# error in request
			request.generateResponseMessage()

		# return response to client and close connection
		request.sendResponse()
		# remove client from socketlist
		self.socketList.remove(connection)


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

		print 'listener serves forever: UID:', os.getuid()

		self.socketList = [self.listener]

		# serve forever
		while 1:
			try:
				print self.socketList
				readReady, writeReady, exceptReady = select.select(self.socketList, [], [])
			except:
				break;

			for readySocket in readReady:
				if readySocket == self.listener:
					conn, addr = self.listener.accept()
					print 'new connection from',addr
					self.socketList.append(conn)
				else:
					self.clientProcessHandler(readySocket)
				

		self.shutdown()

	def shutdown (self):
		self.listener.close()


port = 80
if len(sys.argv) > 1:
	port = int(sys.argv[1])

SecureWebServer(1000,1000,port)

