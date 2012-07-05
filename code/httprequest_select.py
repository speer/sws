import re
import os
from os import path, sep, stat
from time import gmtime, strftime
import subprocess
import cPickle
import socket
import urllib
import threading

# not python standard lib - for mime type detection
import magic

# this class is a wrapper for the request and response object, in order to be pickled and sent over sockets
class RequestResponseWrapper:

	def __init__ (self, request, response):
		self.request = request
		self.response = response

# this class represents a request object, i.e. a parsed version of the requestmessage
class Request:

	def __init__ (self):
		# dictionary of header fields
		self.headers = {}
		# dictionary of environment variables provided to CGI scripts
		self.cgiEnv = {}
		# method (GET, HEAD, POST)
		self.method = None
		# request URI
		self.uri = None
		# filepath of the accessed resource
		self.filepath = ''
		# pathinfo variable for cgi scripts
		self.cgiPathInfo = None
		# used protocol in the request (HTTP/1.X)
		self.protocol = None
		# query part of the URI
		self.query = ''
		# body of the request
		self.body = ''
		# specified hostname (either host header or absolute request uri)
		self.host = None
		# ip address of the client
		self.remoteAddr = None
		# fully qualified domain name of the client
		self.remoteFqdn = None
		# remote port (of the client)
		self.remotePort = None
		# server port
		self.serverPort = None
		# ip address of the server
		self.serverAddr = None

	def getHeader(self,key):
		if key.title() in self.headers:
			return self.headers[key.title()]
		else:
			return None

	def setHeader(self,key,value):
		self.headers[key.title()] = value

	def getContentLength(self):
		contentLength = 0
		try:
			contentLength = int(self.getHeader('content-length'))
		except Exception:
			pass
		return contentLength


# this class represents a response object from which a HTTP response message can be created
class Response:
	
	def __init__ (self):
		# dictionary of header fields
		self.headers = {}
		# dictionary of header fields provided in the response of a cgi script
		self.cgiHeaders = {}
		# statuscode of the request (HTTP/1.1 200 OK)
		self.statusCode = 200
		# statusMessage of the request (HTTP/1.1 200 OK)
		self.statusMessage = 'OK'
		# content-length of the response
		self.contentLength = 0
		# content-type of the response
		self.contentType = None

		# message to be flushed to client
		self.message = ''
		# True when CGI local location redirect
		self.reprocess = False
		# True when the first chunks of data have been sent to client/listener, i.e. status, etc.
		self.flushed = False
		# Becomes true when last chunk of data was sent to listener
		self.connectionClose = False

	def getHeader(self,key):
		if key.title() in self.headers:
			return self.headers[key.title()]
		else:
			return None

	def setHeader(self,key,value):
		self.headers[key.title()] = value

	def getCGIHeader(self,key):
		if key.title() in self.cgiHeaders:
			return self.cgiHeaders[key.title()]
		else:
			return None

	def setCGIHeader(self,key,value):
		self.cgiHeaders[key.title()] = value


# This class contains the main HTTP functionality (parsing, etc.)
class HttpRequest:

	SOCKET_BUF_SIZE = 8192

	SERVER_NAME = 'SWS/0.1'
	SERVER_ADMIN = 'stefan@peerweb.it'
	DOCUMENT_ROOT = '/home/stefan/sws/docs'
	CGI_ROOT = 'cgi-bin'
	DIRECTORY_INDEX = ['index.html','index.php','home.html','env.pl']
	ERRORDOCUMENT_ROOT = '/home/stefan/sws/errordocs'
	ERRORDOCUMENTS = {
		403:{'msg':'Forbidden','file':'403.html','defaulttxt':'Status 403 - Forbidden. You are not allowed to access this resource.'},
		404:{'msg':'Not Found','file':'404.html','defaulttxt':'Status 404 - File Not Found'},
		500:{'msg':'Internal Server Error','file':'500.html','defaulttxt':'Status 500 - Internal Server Error'}
	}

	CONNECTION_TYPE = 'close'
	CGI_PROTOCOL = 'CGI/1.1'
	HTTP_PROTOCOL = 'HTTP/1.1'
	ACCEPTED_PROTOCOLS = ['HTTP/1.0','HTTP/1.1']
	ACCEPTED_REQUEST_TYPES = ['GET','HEAD','POST']
	CGI_SCRIPT_TIMEOUT = 5

	# enabling this results to poor performance
	FQDN_LOOKUP_ENABLED = False

        def __init__ (self, connection):
		# Socket connection, either to client or to listener
		self.connection = connection
		# True when the connection was closed
		self.connectionClosed = False
		# request and response objects
		self.request = Request()
		self.response = Response()
		# temporary received/sent data (used for select system call)
		self.tmpData = ''
		# received request header
		self.requestHeader = ''
		# received request body
		self.requestBody = ''
		# True when the request header was successfully received 
		self.headerReceived = False

	# determines connection specific variables
	def determineHostVars (self):
		self.request.serverAddr = self.connection.getsockname()[0]
		self.request.serverPort = self.connection.getsockname()[1]
		self.request.remoteAddr = self.connection.getpeername()[0]
		self.request.remotePort = self.connection.getpeername()[1]
		if HttpRequest.FQDN_LOOKUP_ENABLED:
			self.request.remoteFqdn = socket.getfqdn(self.request.remoteAddr)
		else:
			self.request.remoteFqdn = self.request.remoteAddr

	def unpickle(self,msg):
		wrapper = cPickle.loads(msg)
		self.request = wrapper.request
		self.response = wrapper.response

	def pickle(self,newResponse=False):
		response = self.response
		if newResponse:
			response = Response()
		data = cPickle.dumps(RequestResponseWrapper(self.request,response))
		return str(len(data))+';'+data


	# receives a pickled request/response wrapper object from the listener and unpickles it
	def receiveRequestFromListener(self):
		data = 'init'
		msg = ''
		msgLength = -1
		while data != '':
                        data = self.connection.recv(HttpRequest.SOCKET_BUF_SIZE)
                        msg = msg + data
			m = re.match(r'(\d+);(.*)',msg,re.DOTALL)
			if m != None and msgLength == -1:
				msgLength = int(m.group(1))
				msg = m.group(2)
			if msgLength <= len(msg):
				# all data received
				break

		# unpickle request
		self.unpickle(msg)
	

	# receives a request message from the client
	# can be called several times and returns true when request was fully received
	def receiveRequestFromClient(self):
		if not self.headerReceived:
			# receive request header
			data = self.connection.recv(HttpRequest.SOCKET_BUF_SIZE)
			self.tmpData = self.tmpData + data
			m = re.match(r'((.+)\r\n\r\n)(.*)',self.tmpData,re.DOTALL)
			if m != None:
				# headers fully received
				self.requestHeader = self.tmpData[:self.tmpData.find('\r\n\r\n')]
				self.requestBody = self.tmpData[self.tmpData.find('\r\n\r\n')+4:]
				return self.parseHeader()
			if data == '':
				return True
			return False
		else:
			# receive request body
			self.requestBody = self.requestBody + self.connection.recv(HttpRequest.SOCKET_BUF_SIZE)
			return self.checkRequestBodyReceived()


	# returns true if the request body was fully received, otherwise false
	def checkRequestBodyReceived(self):
		if len(self.requestBody) >= self.request.getContentLength():
			self.request.body = self.requestBody
			return True
		else:
			return False
		

	# parses the header message
	# if there was a syntax error (400) or the request (incl.) body was fully received, it returns true
	# if the request header syntax is OK, but just parts of the body arrived, it returns false
	def parseHeader(self):
		self.headerReceived = True
		self.requestHeader = self.requestHeader.lstrip()
		lines = self.requestHeader.split('\r\n')
		first = True
		for line in lines:
			line = line.strip()
			line = re.sub('\s{2,}', ' ', line)
			if first:
				# request line
				words = line.split(' ')
				if len(words) != 3:
					self.setBadRequestError('Status 400 - Bad Request Line')
					return True
				self.request.method = words[0].upper()
				self.parseURI(words[1])
				self.request.protocol = words[2].upper()
				first = False
			else:
				if (line == ''):
					break

				# header line
				pos = line.find(':')
				if pos <= 0 or pos >= len(line)-1:
					self.setBadRequestError('Status 400 - Bad Header')
					return True
				key = line[0:pos].strip()
				value = line[pos+1:len(line)].strip()
				self.request.setHeader(key,value)

		# determine host
		if self.request.host == None:
			h = self.request.getHeader('host')
			if h != None:
				m = re.match(r'([\w\-\.]+)(:(\d+))?',h)
				if m != None:
					self.request.host = m.group(1)

		# check if POST message has a message body
		if self.request.method == 'POST' and self.request.getContentLength() > 0:
			return self.checkRequestBodyReceived()
		
		return True

		
	# parses an URI (ex. GET / HTTP/1.1) and sets uri, query, host and filepath variables
	def parseURI(self,uri):
		if re.match('[hH][tT][tT][pP][sS]?://',uri) == None:
			# absolute path - host determined afterwards
			m = re.match(r'([^\?]*)(\?(.*))?',uri)
			if m != None:
				self.request.uri = m.group(1)
				self.request.query = m.group(3)
		else:
			# absolute uri / determines host
			m = re.match(r'[hH][tT][tT][pP]([sS])?://([\w\-\.]+)(:(\d+))?([^\?]*)(\?(.*))?',uri)
			if m != None:
				self.request.host = m.group(2)
				self.request.uri = m.group(5)
				self.request.query = m.group(7)

		# query supposed to be empty if not specified
		if self.request.query == None:
			self.request.query = ''

		self.request.filepath = path.abspath(HttpRequest.DOCUMENT_ROOT + sep + self.request.uri)


	# checks if the request is valid so far, or if there are already syntax errors somewhere
	def checkValidity(self):
		if self.response.statusCode != 200:
			return False
		if self.request.method not in HttpRequest.ACCEPTED_REQUEST_TYPES:
			self.setBadRequestError('Status 400 - Command not supported')
			return False
		if self.request.protocol not in HttpRequest.ACCEPTED_PROTOCOLS:
			self.setBadRequestError('Status 400 - Version not supported')
			return False
		if self.request.host == None:
			self.setBadRequestError('Status 400 - No Host specified')
			return False
		return True


	# uses the magic library to determine the mimetype of a file
	# it does not look at the file extension, but at the content of the file
	def getContentTypeFromFile(self,filename):
		try:
			mime = magic.Magic(mime=True)
			mime_encoding = magic.Magic(mime_encoding=True)
			contentType = mime.from_file(filename)
			charset = mime_encoding.from_file(filename)
			if charset != 'binary':
				return contentType + ';charset=' + charset
			else:
				return contentType
		except Exception:
			return 'application/octet-stream'


	# determines and sets environment variables, provided to cgi scripts
	def generateCGIEnvironment(self):
		contentLength = self.request.getContentLength()
		if contentLength > 0:
			self.request.cgiEnv['CONTENT_LENGTH'] = str(contentLength)

		contentType = self.request.getHeader('Content-Type')
		if contentType != None:
			self.request.cgiEnv['CONTENT_TYPE'] = contentType
	
		self.request.cgiEnv['GATEWAY_INTERFACE'] = HttpRequest.CGI_PROTOCOL
		if self.request.cgiPathInfo != None:
			self.request.cgiEnv['PATH_INFO'] = self.request.cgiPathInfo
			self.request.cgiEnv['PATH_TRANSLATED'] = path.abspath (HttpRequest.DOCUMENT_ROOT + sep + self.request.cgiPathInfo)
		self.request.cgiEnv['QUERY_STRING'] = self.request.query
		self.request.cgiEnv['REMOTE_ADDR'] = self.request.remoteAddr
		self.request.cgiEnv['REMOTE_HOST'] = self.request.remoteFqdn
		self.request.cgiEnv['REQUEST_METHOD'] = self.request.method
		self.request.cgiEnv['SCRIPT_NAME'] = self.request.filepath[len(HttpRequest.DOCUMENT_ROOT):]
		self.request.cgiEnv['SERVER_NAME'] = self.request.host
		self.request.cgiEnv['SERVER_PORT'] = str(self.request.serverPort)
		self.request.cgiEnv['SERVER_PROTOCOL'] = HttpRequest.HTTP_PROTOCOL
		self.request.cgiEnv['SERVER_SOFTWARE'] = HttpRequest.SERVER_NAME
		self.request.cgiEnv['DOCUMENT_ROOT'] = HttpRequest.DOCUMENT_ROOT
		self.request.cgiEnv['SERVER_ADMIN'] = HttpRequest.SERVER_ADMIN
		self.request.cgiEnv['SERVER_ADDR'] = self.request.serverAddr
		self.request.cgiEnv['SCRIPT_FILENAME'] = self.request.filepath
		if self.request.query == '':
			self.request.cgiEnv['REQUEST_URI'] = self.request.uri
		else:
			self.request.cgiEnv['REQUEST_URI'] = self.request.uri + '?' + self.request.query
		self.request.cgiEnv['REMOTE_PORT'] = str(self.request.remotePort)
		self.request.cgiEnv['PATH'] = os.environ['PATH']
		
		# map all http headers to environment variables
		for keys in self.request.headers.keys():
			self.request.cgiEnv['HTTP_'+keys.replace('-','_').upper()] = self.request.headers[keys]


	# generates the header message of the response, considering status line and all response header fields
	def generateResponseHeaderMessage(self):
		# generate response headers
		self.response.setHeader('Date',strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime()))
		self.response.setHeader('Server',HttpRequest.SERVER_NAME)
		self.response.setHeader('Connection',HttpRequest.CONNECTION_TYPE)
		
		# determine contentlength
		if self.response.contentLength > 0:
			self.response.setHeader('Content-Length', str(self.response.contentLength))

		# set content-length if not a cgi script
		if len(self.response.cgiHeaders) == 0:
			self.response.setHeader('Content-Type', self.response.contentType)
		else:
			# add cgi headers to response
			for key in self.response.cgiHeaders.keys():
				self.response.setHeader(key,self.response.cgiHeaders[key])

		# generate Status line
		m = HttpRequest.HTTP_PROTOCOL+' '+str(self.response.statusCode)+' '+self.response.statusMessage+'\r\n'

		# add headers
		for key in self.response.headers.keys():
			m = m + key + ':' + self.response.headers[key]+'\r\n'

		self.response.message = m + '\r\n'


	# appends the body to the response message if the request command was not HEAD
	def appendResponseMessageBody(self,body):
		if self.request.method != 'HEAD':
			self.response.message = self.response.message + body


	# sends an error back to the listener process
	# if an errorMessage is provided, this message will be shown instead of the errorDocument
	def sendError(self, errorCode, errorMessage=None):
		self.response.cgiHeaders = {}
		if errorCode in HttpRequest.ERRORDOCUMENTS:
			self.response.statusCode = errorCode
		else:
			self.response.statusCode = 500
		self.response.statusMessage = HttpRequest.ERRORDOCUMENTS[self.response.statusCode]['msg']

		errorFile = path.abspath(HttpRequest.ERRORDOCUMENT_ROOT + sep + HttpRequest.ERRORDOCUMENTS[self.response.statusCode]['file'])

		# check if errordocument is a valid file and no other message has been set
		if errorMessage == None and self.isJailedInto(HttpRequest.ERRORDOCUMENT_ROOT,errorFile) and os.path.isfile(errorFile):
			try:
				self.response.contentType = self.getContentTypeFromFile(errorFile)
				self.response.contentLength = os.path.getsize(errorFile)
				self.generateResponseHeaderMessage()
				# if it is a HEAD request, there is no need to access the errordocument
				if self.request.method != 'HEAD':
					self.accessFile(errorFile)
				else:
					self.flushResponseToListener(True)
				return
			except:
				if self.response.flushed:
					return
				# if not flushed, try to flush standard message (defaulttxt)

		self.response.contentType = 'text/plain'
		if errorMessage == None:
			errorMessage = HttpRequest.ERRORDOCUMENTS[self.response.statusCode]['defaulttxt']
		self.response.contentLength = len(errorMessage)
		self.generateResponseHeaderMessage()
		self.appendResponseMessageBody(errorMessage)
		self.flushResponseToListener(True)


	# prepares an 400 Bad Request response, showing the provided errorMessage
	def setBadRequestError(self, errorMessage):
		self.response.statusCode = 400
		self.response.statusMessage = 'Bad Request'
		self.response.contentType = 'text/plain'
		self.response.contentLength = len(errorMessage)
		self.generateResponseHeaderMessage()
		self.response.connectionClose = True
		self.appendResponseMessageBody(errorMessage)


	# sends the response message to the client
	# returns true when the whole message was sent
	def flushResponseToClient(self):
		try:
			byteswritten = self.connection.send(self.response.message)
			self.response.message = self.response.message[byteswritten:]
			return len(self.response.message) == 0
		except:
			self.response.connectionClose = True
			return True


	# sends a pickled request/response wrapper object to the listener process
	# if closeConnection is set, that means that the connection will be closed after sending
	def flushResponseToListener(self, closeConnection=False):
		try:
			self.response.connectionClose = closeConnection
			self.connection.send(self.pickle())
			self.response.flushed = True
			self.response.message = ''
			if closeConnection:
				self.connection.close()
				self.connectionClosed = True
		except:
			self.connection.close()
			self.connectionClosed = True


	# checks whether path is jailed into the jail
	def isJailedInto(self, jail, path):
		return path.startswith(jail + sep) or path == jail


	# processes the request, i.e. determines whether a CGI script or a normal resource was accessed
	def process (self):
		# check if resource is inside the documentroot (jail)
		if self.isJailedInto(HttpRequest.DOCUMENT_ROOT, self.request.filepath):
			# check if resource is a cgi script
			if self.isJailedInto(HttpRequest.DOCUMENT_ROOT + sep + HttpRequest.CGI_ROOT, self.request.filepath):
				self.processCGI()
			else:
				self.processDocument()
		else:
			self.sendError(403)

	# processes a normal resource request
	def processDocument(self):
		# check directoryIndex if path is a directory
		if os.path.isdir(self.request.filepath):
			for index in HttpRequest.DIRECTORY_INDEX:
				f = path.abspath (self.request.filepath + sep + index)
				if os.path.isfile(f):
					self.request.filepath = f
					break

		# check if resource is a valid file
		if os.path.isfile(self.request.filepath):
			try:
				self.response.contentType = self.getContentTypeFromFile(self.request.filepath)
				self.response.contentLength = os.path.getsize(self.request.filepath)
				self.generateResponseHeaderMessage()
				# HEAD request must not have a response body, no need to access file
				if self.request.method != 'HEAD':
					self.accessFile(self.request.filepath)
				else:
					self.flushResponseToListener(True)
			except:
				self.sendError(500)

		# if a directory is accessed, deliver 403: Forbidden error
		elif os.path.isdir(self.request.filepath):
			self.sendError(403)
		# else deliver a 404: Not Found error
		else:
			self.sendError(404)


	# accesses a resource and sends the content back to the listener in chunks of data, i.e. not all at once
	# at the last "flush" the connection to the listener will be closed
	def accessFile(self, filename):
		f = file(filename,'r')

		# check owner of the file
		st = os.stat(filename)
		# remove privileges
		os.setgid(st.st_gid)
		os.setuid(st.st_uid)

		data = f.read(HttpRequest.SOCKET_BUF_SIZE)
		nextData = f.read(HttpRequest.SOCKET_BUF_SIZE)
		while nextData and not self.connectionClosed:
			self.response.message = self.response.message + data
			# flush data part to listener and keep connection open
			self.flushResponseToListener()
			data = nextData
			nextData = f.read(HttpRequest.SOCKET_BUF_SIZE)
		self.response.message = self.response.message + data
		# flush last data part to listener and close connection
		self.flushResponseToListener(True)
		f.close()


	# processes a CGI script request
	def processCGI(self):
		# determine path (PATH_INFO, PATH_TRANSLATE)
		cgiAbsRoot = HttpRequest.DOCUMENT_ROOT + sep + HttpRequest.CGI_ROOT
		uri = self.request.filepath[len(cgiAbsRoot):]
		lines = uri.split('/')
		cgiScriptPath = cgiAbsRoot
		for line in lines:
			if line == '':
				continue
			cgiScriptPath = cgiScriptPath + sep + line
			if os.path.isfile(cgiScriptPath):
				break
		if cgiScriptPath != self.request.filepath:
			self.request.cgiPathInfo = urllib.unquote(self.request.filepath[len(cgiScriptPath):])
			self.request.filepath = cgiScriptPath

		# check directoryIndex if path is a directory
		if os.path.isdir(self.request.filepath):
			for index in HttpRequest.DIRECTORY_INDEX:
				f = path.abspath (self.request.filepath + sep + index)
				if os.path.isfile(f):
					self.request.filepath = f
					break

		# check if resource is a valid file
		if os.path.isfile(self.request.filepath):
			try:
				# check owner of the file
				st = os.stat(self.request.filepath)
				# remove privileges
				os.setgid(st.st_gid)
				os.setuid(st.st_uid)

				# check whether resource is an executable file
		        	if not os.access(self.request.filepath, os.X_OK):
					self.sendError(500)
					return

				# check if resource is owned by someone except root
				st = os.stat(self.request.filepath)
				if st.st_uid == 0:
					self.sendError(500)
					return

				# generate environment variables for the CGI script
				self.generateCGIEnvironment()

				# execute cgi script - abort timeout of n seconds
				success, cgiBody = self.parseCGIResponse(CGIExecutor(self).execute(HttpRequest.CGI_SCRIPT_TIMEOUT))

				# if execution was successful and no error was sent already
				if success:
					self.response.contentLength = len(cgiBody)
					self.generateResponseHeaderMessage()
					self.appendResponseMessageBody(cgiBody)
					self.flushResponseToListener(True)
				
			except:
				# Exception will be raised by the CGIExecutor if CGI Script takes to much time
				self.sendError(500,'Status 500 - CGI script aborted because of timeout')

		elif os.path.isdir(self.request.filepath):
			# if resource is a directory, send 403: Forbidden error
			self.sendError(403)
		else:
			# send 404: Not Found error if resource is not found
			self.sendError(404)


	# parses the response of the CGI script 
	# returns the pair (success,cgiBody)
	def parseCGIResponse(self,document):
		document = document.lstrip()
		cgiBody = ''
		m = re.match(r'((.+)\n\n)(.*)',document,re.DOTALL)
		if m != None:
			header = document[:document.find('\n\n')]
			body = document[document.find('\n\n')+2:]
			# parse header
			lines = header.split('\n')
			for line in lines:
				line = line.strip()
				line = re.sub('\s{2,}', ' ', line)
				pos = line.find(':')
				if pos <= 0 or pos >= len(line)-1:
					self.sendError(500,'Status 500 - Bad Header in CGI response')
					return (False,'')
				key = line[0:pos].strip()
				value = line[pos+1:len(line)].strip()
				self.response.setCGIHeader(key,value)

			if len(self.response.cgiHeaders) == 0:
				self.sendError(500,'Status 500 - CGI Script has no headers')
				return (False,'')

			location = self.response.getCGIHeader('Location')
			if location == None:
				# document response (RFC: 6.2.1)
				if body != None and body != '':
					if self.response.getCGIHeader('Content-Type') == None:
						# content-type must be specified
						self.sendError(500,'Status 500 - CGI Script must specify content type')
						return (False,'')

					cgiBody = body

				# check for status header field
				if self.response.getCGIHeader('Status') != None:
					s = re.match(r'(\d+) (.*)',self.response.getCGIHeader('Status'),re.DOTALL)
					if s != None:
						self.response.statusCode = int(s.group(1))
						self.response.statusMessage = s.group(2)

			else:
				# redirect response
				if location.startswith('/'):
					# local redirect response (RFC: 6.2.2)
					self.response.reprocess = True
					newEnv = {}
					if self.request.cgiPathInfo != None:
						newEnv['REDIRECT_URL'] = self.request.filepath[len(HttpRequest.DOCUMENT_ROOT):] + self.request.cgiPathInfo
					else:
						newEnv['REDIRECT_URL'] = self.request.filepath[len(HttpRequest.DOCUMENT_ROOT):]
					newEnv['REDIRECT_STATUS'] = str(self.response.statusCode)
					# rename CGI environment variables
					for key in self.request.cgiEnv.keys():
						newEnv['REDIRECT_'+key] = self.request.cgiEnv[key]
					self.request.cgiEnv = newEnv
				else:
					# client redirect response (RFC: 6.2.3, 6.2.4)
					self.response.statusCode = 302
					self.response.statusMessage = 'Found'
					self.response.setHeader('Location',location)

					if body != None and body != '':
						if self.response.getCGIHeader('Content-Type') == None:
							# content-type must be specified
							self.sendError(500,'Status 500 - CGI Script must specify content type')
							return (False,'')
						# success
						cgiBody = body
		else:
			self.sendError(500,'Status 500 - CGI returned wrong response')
			return (False,'')

		return (True,cgiBody)


	# checks whether the CGI response contained the Location header and it is a local redirect response
	# returns true if that is the case, otherwise false
	# additionally it monitors eventual endless loops that might occur if a cgiscript forwards to itself
	def checkReprocess(self):
		#Location flag set in CGI script
		if self.response.reprocess and self.response.getCGIHeader('Location') != None:
			# CGI local redirect response (RFC 6.2.2)
			curHost = self.request.host
			curUri = self.request.uri
			curQuery = self.request.query
			self.parseURI(self.response.getCGIHeader('Location'))
			# check for recursion, but may still happen
			if self.request.host == curHost and self.request.uri == curUri and self.request.query == curQuery:
				self.sendError(500,'Status 500 - recursion in CGI script')
				return False
			return True
		else:
			return False


# This class provides an execution environment to the CGI script, which monitors the time it takes and aborts the script if it takes too long
class CGIExecutor():

	def __init__ (self, request):
		# Script process
		self.process = None
		# HttpRequest object
		self.request = request
		# Response of the CGI script
		self.response = None


	# executes the CGI script in a thread, which creates a new process that executes the requested scriptfile
	# the thread will cause the process to terminate after a timeout
	def execute (self, timeout=30):
		
		# executed in a separate thread
		def cgiThread():
			# creates a new process, running the script
	        	self.process = subprocess.Popen([self.request.request.filepath],stdout=subprocess.PIPE,stdin=subprocess.PIPE,env=self.request.request.cgiEnv)

			# eventual POST data goes to stdin
			if self.request.request.body != '':
				self.process.stdin.write(self.request.request.body)

			# the response is on standardoutput
			self.response = self.process.communicate()[0]

		thread = threading.Thread(target=cgiThread)
		thread.start()
		thread.join(timeout)
		# if thread is still alive after timeout means that the script took to long
		if thread.is_alive():
			self.process.terminate()
			thread.join()
			raise Exception

		return self.response
