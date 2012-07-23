import re
import os
from os import path, sep, stat
from time import gmtime, strftime
import subprocess
import cPickle
import socket
import urllib
import threading
import logging

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
		# virtualhost that matches the request
		self.virtualHost = None
		# cgi directory matching the request
		self.cgiDirectory = None
		# executor for the cgi request (ex /bin/bash)
		self.cgiExecutor = None
		# list of matching directory directives for this request
		self.directoryChain = ['/']

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

	SERVER_NAME = 'SWS/1.0'
	CGI_PROTOCOL = 'CGI/1.1'
	HTTP_PROTOCOL = 'HTTP/1.1'
	ACCEPTED_PROTOCOLS = ['HTTP/1.0','HTTP/1.1']
	ACCEPTED_REQUEST_TYPES = ['GET','HEAD','POST']

        def __init__ (self, connection, config):
		# object which contains the configuration of the server
		self.config = config
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
		# used to prevent cgi endless recursions
		self.requestNumber = 1
		# Output Filter Processor
		self.ofProcessor = OutputFilterProcessor(self)


	# log into access-log file
	def logAccess(self):
		referer = '-'
		useragent = '-'
		host = '-'
		req = '-'
		if self.request.getHeader ('referer') != None:
			referer = self.request.getHeader('referer')
		if self.request.getHeader ('user-agent') != None:
			useragent = self.request.getHeader('user-agent')
		if self.request.host != None:
			host = self.request.host
		if self.request.method != None and self.request.uri != None and self.request.protocol != None:
			req = self.request.method + ' ' + self.request.uri + ' ' + self.request.protocol

		logging.getLogger(self.request.virtualHost).info('%s:%i %s - - [%s] "%s" %i %i "%s" "%s"' % (host,self.request.serverPort,self.request.remoteAddr,strftime("%d/%b/%Y:%H:%M:%S %z"),req,self.response.statusCode,self.response.contentLength,referer,useragent))


	# log into error-log file
	def logError(self, message):
		logging.getLogger(self.request.virtualHost).error('[%s] [error] [client %s] %s' % (strftime("%a %b %d %H:%M:%S %Y"), self.request.remoteAddr, message))


	# determines connection specific variables
	def determineHostVars (self):
		self.request.serverAddr = self.connection.getsockname()[0]
		self.request.serverPort = self.connection.getsockname()[1]
		self.request.remoteAddr = self.connection.getpeername()[0]
		self.request.remotePort = self.connection.getpeername()[1]
		if self.config.configurations['hostnamelookups']:
			self.request.remoteFqdn = socket.getfqdn(self.request.remoteAddr)
		else:
			self.request.remoteFqdn = self.request.remoteAddr
		# initialize virtualhost to default virtualhost
		self.request.virtualHost = self.config.defaultVirtualHost

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
                        data = self.connection.recv(self.config.configurations['socketbuffersize'])
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
			data = self.connection.recv(self.config.configurations['socketbuffersize'])
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
			self.requestBody = self.requestBody + self.connection.recv(self.config.configurations['socketbuffersize'])
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
					self.setBadRequestError('Bad Request Line')
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
					self.setBadRequestError('Bad Header')
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

		# determine filepath and virtualhost
		self.determineFilepath()

		# check if POST message has a message body
		if self.request.method == 'POST' and self.request.getContentLength() > 0:
			return self.checkRequestBodyReceived()
		
		return True

	# determines virtualhost and filepath
	def determineFilepath(self):
		for vHost in self.config.virtualHosts.keys():
			if self.config.virtualHosts[vHost]['servername'] == self.request.host or self.request.host in self.config.virtualHosts[vHost]['serveralias']:
				self.request.virtualHost = vHost
				break

		self.request.filepath = path.abspath(self.config.virtualHosts[self.request.virtualHost]['documentroot'] + sep + self.request.uri)

	# determines the chain of matching directories
	def determineDirectoryChain(self):
		self.request.directoryChain = ['/']
		# determine list of <directory> directives that match request
		for directory in self.config.virtualHosts[self.request.virtualHost]['directory'].keys():
			dirPath = path.abspath(self.config.virtualHosts[self.request.virtualHost]['documentroot'] + sep + directory)
			if not os.path.isdir(dirPath):
				continue

			if self.isJailedInto(dirPath,self.request.filepath):
				self.request.directoryChain.append(directory)

		self.request.directoryChain.sort(reverse=True)

	# checks whether path is jailed into the jail
	def isJailedInto(self, jail, path):
		return path.startswith(jail + sep) or path == jail

	# updates filename according to a directoryindex
	def determineDirectoryIndex(self):
		# check for matching directoryindex
		if not os.path.isdir(self.request.filepath):
			return
		for directory in self.request.directoryChain:
			# if no directoryindex in current directory, search again one level up
			if len(self.config.virtualHosts[self.request.virtualHost]['directory'][directory]['directoryindex']) == 0:
				if self.config.virtualHosts[self.request.virtualHost]['directory'][directory]['stopinheritation']['directoryindex']:
					break
				else:
					continue
			# if directoryindex specified, search for match and then stop in any case
			for index in self.config.virtualHosts[self.request.virtualHost]['directory'][directory]['directoryindex']:
				f = path.abspath (self.request.filepath + sep + index)
				if os.path.isfile(f):
					self.request.filepath = f
			return

	def determinePathInfoCGI(self):
		# determine path (PATH_INFO, PATH_TRANSLATE)
		cgiRoot = path.abspath(self.config.virtualHosts[self.request.virtualHost]['documentroot'] + sep + self.request.cgiDirectory)
		uri = self.request.filepath[len(cgiRoot):]
		lines = uri.split('/')
		cgiScriptPath = cgiRoot
		for line in lines:
			if line == '':
				continue
			cgiScriptPath = cgiScriptPath + sep + line
			if os.path.isfile(cgiScriptPath):
				break
		if cgiScriptPath != self.request.filepath:
			self.request.cgiPathInfo = urllib.unquote(self.request.filepath[len(cgiScriptPath):])
			self.request.filepath = cgiScriptPath

	def determineCGIDirectory(self):
		self.request.cgiDirectory = None
		# check for matching folders
		for directory in self.request.directoryChain:
			# if no cgi-handler in current directory, search again one level up
			if len(self.config.virtualHosts[self.request.virtualHost]['directory'][directory]['cgihandler']) == 0:
				if self.config.virtualHosts[self.request.virtualHost]['directory'][directory]['stopinheritation']['cgihandler']:
					break
				else:
					continue
			# if cgi-handler specified, set cgiDirectory and stop
			self.request.cgiDirectory = directory
			break

	def determineOutputFilterDirectory(self):
		self.ofProcessor.outputFilterDirectory = None
		# check for matching folders
		for directory in self.request.directoryChain:
			# if no output filter in current directory, search again one level up
			if len(self.config.virtualHosts[self.request.virtualHost]['directory'][directory]['setoutputfilter']) == 0:
				if self.config.virtualHosts[self.request.virtualHost]['directory'][directory]['stopinheritation']['setoutputfilter']:
					break
				else:
					continue
			# if output filter specified, set outputFilterDirectory and stop
			self.ofProcessor.outputFilterDirectory = directory
			break

	# determine request properties and check validity
	def checkRequest(self):
		self.request.cgiExecutor = None

		# check whether directory specifies any CGI handler
		self.determineCGIDirectory()

		# check whether directory specifies any Output filters
		self.determineOutputFilterDirectory()

		# request is inside a cgi directory
		if self.request.cgiDirectory != None and self.response.statusCode < 400:
			# check pathinfo for regular requests, not used for errordocuments
			self.determinePathInfoCGI()

		# check directoryIndex if path is a directory
		self.determineDirectoryIndex()

		# check if resource is a valid file
		if not os.path.isfile(self.request.filepath):
			# if a directory is accessed, deliver 403: Forbidden error
			if os.path.isdir(self.request.filepath):
				return 403
			# else deliver a 404: Not Found error
			else:
				return 404

		if self.request.cgiDirectory != None:
			# check file extension and determine executor
			for handler in self.config.virtualHosts[self.request.virtualHost]['directory'][self.request.cgiDirectory]['cgihandler']:
				if self.request.filepath.endswith(handler['extension']):
					self.request.cgiExecutor = handler['executor']
					return -1

		return -2


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


	# checks if the request is valid so far, or if there are already syntax errors somewhere
	def checkValidity(self):
		if self.response.statusCode != 200:
			return False
		if self.request.method not in HttpRequest.ACCEPTED_REQUEST_TYPES:
			self.setBadRequestError('Command not supported')
			return False
		if self.request.protocol not in HttpRequest.ACCEPTED_PROTOCOLS:
			self.setBadRequestError('Version not supported')
			return False
		if self.request.host == None:
			self.setBadRequestError('No Host specified')
			return False
		return True


	# returns a matching content type, considering the virtualhosts config file, otherwise none
	def getVHConfigContentType(self):
		if self.request.virtualHost != None:
			for directory in self.request.directoryChain:
				dirtypes = self.config.virtualHosts[self.request.virtualHost]['directory'][directory]['addtype']
				if len(dirtypes) == 0:
					if self.config.virtualHosts[self.request.virtualHost]['directory'][directory]['stopinheritation']['addtype']:
						break
					else:
						continue
				for typ in dirtypes.keys():
					if self.request.filepath.endswith(typ):
						return dirtypes[typ]
		return None

	# returns a matching content type, considering the main config file, otherwise none
	def getMainConfigContentType(self):
		for typ in self.config.configurations['addtype'].keys():
			if self.request.filepath.endswith(typ):
				return self.config.configurations['addtype'][typ]
		return None


	# uses the magic library to determine the mimetype of a file or eventual configuration directives
	def determineContentType(self):
		contentType = self.getVHConfigContentType()
		if contentType == None:
			contentType = self.getMainConfigContentType()
		if contentType == None:
			try:
				mime = magic.Magic(mime=True)
				contentType = mime.from_file(self.request.filepath)
			except Exception:
				contentType = self.config.configurations['defaulttype']

		try:
			mime_encoding = magic.Magic(mime_encoding=True)
			charset = mime_encoding.from_file(self.request.filepath)
			if charset != 'binary':
				return contentType + ';charset=' + charset
		except Exception:
			pass
		return contentType


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
			self.request.cgiEnv['PATH_TRANSLATED'] = path.abspath (self.config.virtualHosts[self.request.virtualHost]['documentroot'] + sep + self.request.cgiPathInfo)
		self.request.cgiEnv['QUERY_STRING'] = self.request.query
		self.request.cgiEnv['REMOTE_ADDR'] = self.request.remoteAddr
		self.request.cgiEnv['REMOTE_HOST'] = self.request.remoteFqdn
		self.request.cgiEnv['REQUEST_METHOD'] = self.request.method
		self.request.cgiEnv['SCRIPT_NAME'] = self.request.filepath[len(self.config.virtualHosts[self.request.virtualHost]['documentroot']):]
		self.request.cgiEnv['SERVER_NAME'] = self.request.host
		self.request.cgiEnv['SERVER_PORT'] = str(self.request.serverPort)
		self.request.cgiEnv['SERVER_PROTOCOL'] = HttpRequest.HTTP_PROTOCOL
		self.request.cgiEnv['SERVER_SOFTWARE'] = HttpRequest.SERVER_NAME
		self.request.cgiEnv['DOCUMENT_ROOT'] = self.config.virtualHosts[self.request.virtualHost]['documentroot'] 
		self.request.cgiEnv['SERVER_ADMIN'] = self.config.virtualHosts[self.request.virtualHost]['serveradmin']
		self.request.cgiEnv['SERVER_ADDR'] = self.request.serverAddr
		self.request.cgiEnv['REDIRECT_STATUS'] = '200'
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
		self.response.setHeader('Connection','close')
		
		# determine contentlength
		if self.response.contentLength > 0 and self.ofProcessor.outputFilterDirectory == None:
			self.response.setHeader('Content-Length', str(self.response.contentLength))

		# set content-type if not a cgi script
		if len(self.response.cgiHeaders) == 0:
			self.response.setHeader('Content-Type', self.response.contentType)
		else:
			# add cgi headers to response
			for key in self.response.cgiHeaders.keys():
				self.response.setHeader(key,self.response.cgiHeaders[key])

		# set headers from configuration, but nor for errordocuments
		if self.request.virtualHost != None and self.response.statusCode < 400:
			for directory in self.request.directoryChain:
				dirheaders = self.config.virtualHosts[self.request.virtualHost]['directory'][directory]['addheader']
				if len(dirheaders) == 0:
					if self.config.virtualHosts[self.request.virtualHost]['directory'][directory]['stopinheritation']['addheader']:
						break
					else:
						continue
				for header in dirheaders.keys():
					self.response.setHeader(header,dirheaders[header])
				break

		# generate Status line
		m = HttpRequest.HTTP_PROTOCOL+' '+str(self.response.statusCode)+' '+self.response.statusMessage+'\r\n'

		# add headers
		for key in self.response.headers.keys():
			m = m + key + ':' + self.response.headers[key]+'\r\n'

		self.response.message = m + '\r\n'

		# log the access
		self.logAccess()


	# appends the body to the response message if the request command was not HEAD
	def appendResponseMessageBody(self,body):
		if self.request.method != 'HEAD':
			self.response.message = self.response.message + body


	# sends an error back to the listener process
	# if an errorMessage is provided, this message will be shown instead of the errorDocument
	def sendError(self, errorCode, errorMessage=None):

		# if headers have been sent already, don't sent errordocument
		if self.response.flushed:
			return

		if self.response.statusCode >= 400:
			# preventing recursions (ex. processCGI calls sendError)
			raise Exception

		self.response.cgiHeaders = {}
		if errorCode in self.config.configurations['errordocument'].keys():
			self.response.statusCode = errorCode
		else:
			self.response.statusCode = 500

		self.response.statusMessage = self.config.configurations['errordocument'][self.response.statusCode]['msg']

		eMsg = errorMessage
		if eMsg == None:
			eMsg = ''
		else:
			eMsg = eMsg + ': '
		eMsg = eMsg + self.request.filepath
		self.logError('%i %s: %s' % (self.response.statusCode, self.response.statusMessage, eMsg))

		errorFile = self.config.virtualHosts[self.request.virtualHost]['errordocument'][self.response.statusCode]
		errorRoot = self.config.virtualHosts[self.request.virtualHost]['errordocumentroot']

		if errorFile != None:
			errorFile = path.abspath(errorRoot + sep + errorFile)

			# check if errordocument is a valid file and no other message has been set
			if  self.isJailedInto(errorRoot,errorFile) and os.path.isfile(errorFile):
				self.request.filepath = errorFile

				# determine chain of matching directories
				self.determineDirectoryChain()

				# check whether request is a CGI request, check documentroot and file existance
				typ = self.checkRequest()

				try:
					if typ == -1:
						self.processCGI()
						return
					elif typ == -2:
						self.processDocument()
						return
				except:
					if self.response.flushed:
						return

		# if not flushed, try to flush message or standard message (defaulttxt)
		self.response.contentType = 'text/plain'
		if errorMessage == None:
			errorMessage = self.config.configurations['errordocument'][self.response.statusCode]['defaulttxt']
		self.response.contentLength = len(errorMessage)
		self.generateResponseHeaderMessage()
		self.appendResponseMessageBody(errorMessage)
		self.flushResponseToListener(True)


	# prepares an 400 Bad Request response, showing the provided errorMessage
	def setBadRequestError(self, errorMessage):
		self.response.cgiHeaders = {}
		self.response.statusCode = 400
		self.response.statusMessage = 'Bad Request'
		self.response.contentType = 'text/plain'
		self.response.contentLength = len(errorMessage)
		self.generateResponseHeaderMessage()
		self.logError('%i %s: %s' % (self.response.statusCode, self.response.statusMessage, errorMessage))
		self.response.connectionClose = True
		self.appendResponseMessageBody(errorMessage)

	# prepares an 500 Internal Server Error response, showing the provided errorMessage
	def setInternalServerError(self, errorMessage):
		self.response.cgiHeaders = {}
		self.response.statusCode = 500
		self.response.statusMessage = 'Internal Server Error'
		self.response.contentType = 'text/plain'
		self.response.contentLength = len(errorMessage)
		self.generateResponseHeaderMessage()
		self.logError('%i %s: %s' % (self.response.statusCode, self.response.statusMessage, errorMessage))
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
			# ofProcessor acts as a message queue if an output filter is specified
			# it accumulates the response body data, to be sent in one go to the filter
			if self.ofProcessor.execute():
				self.connection.send(self.pickle())
			self.response.flushed = True
			self.response.message = ''
			if closeConnection:
				self.connection.close()
				self.connectionClosed = True
		except:
			self.connection.close()
			self.connectionClosed = True	


	# processes the request, i.e. determines whether a CGI script or a normal resource was accessed
	def process (self):
		# check if resource is inside the documentroot (jail)
		if self.isJailedInto(self.config.virtualHosts[self.request.virtualHost]['documentroot'], self.request.filepath):
			# determine chain of matching directories
			self.determineDirectoryChain()

			# check whether request is a CGI request, check documentroot and file existance
			typ = self.checkRequest()

			if typ == -1:
				self.processCGI()
			elif typ == -2:
				self.processDocument()
			else:
				self.sendError(typ)
		else:
			self.sendError(403,'Not allowed to access resource outside documentroot')


	# processes a normal resource request
	def processDocument(self):
		try:
			# privilege separation
			self.removePrivileges()
			self.response.contentType = self.determineContentType()
			self.response.contentLength = os.path.getsize(self.request.filepath)
			self.generateResponseHeaderMessage()
			# HEAD request must not have a response body, no need to access file
			if self.request.method != 'HEAD':
				self.accessFile(self.request.filepath)
			else:
				self.flushResponseToListener(True)
		except:
			self.sendError(500)


	# accesses a resource and sends the content back to the listener in chunks of data, i.e. not all at once
	# at the last "flush" the connection to the listener will be closed
	def accessFile(self, filename):
		f = file(filename,'r')

		data = f.read(self.config.configurations['socketbuffersize'])
		nextData = f.read(self.config.configurations['socketbuffersize'])
		while nextData and not self.connectionClosed:
			self.response.message = self.response.message + data
			# flush data part to listener and keep connection open
			self.flushResponseToListener()
			data = nextData
			nextData = f.read(self.config.configurations['socketbuffersize'])
		self.response.message = self.response.message + data
		# flush last data part to listener and close connection
		self.flushResponseToListener(True)
		f.close()


	def removePrivileges(self):
		st = os.stat(self.request.filepath)
		# don't remove privileges if process has already limited privileges
		if os.getuid() == 0:
			# if file is owned by root try to access is as default user
			if st.st_uid == 0:
				# default user
				os.setgid(self.config.configurations['group'])
				os.setuid(self.config.configurations['user'])
			else:
				# file owner user
				os.setgid(st.st_gid)
				os.setuid(st.st_uid)


	# processes a CGI script request
	def processCGI(self):
		try:
			self.removePrivileges()

			# check whether resource is an executable file (if no cgi executor set)
	        	if self.request.cgiExecutor == None and not os.access(self.request.filepath, os.X_OK):
				self.sendError(500,'CGI Script is not accessible/executable')
				return

			# generate environment variables for the CGI script
			self.generateCGIEnvironment()

			# execute cgi script - abort timeout of n seconds
			status = CGIExecutor(self).execute()

			# if execution was successful and no error was sent already
			if status == -1:
				self.sendError(500,'CGI Script aborted because of timeout')
		except:
			# Exception raised by the CGI executor
			self.sendError(500,'CGI script execution aborted')



	# checks whether the CGI response contained the Location header and it is a local redirect response
	# returns true if that is the case, otherwise false
	# additionally it monitors eventual endless loops that might occur if a cgiscript forwards to itself
	def checkReprocess(self):
		#Location flag set in CGI script
		if self.response.reprocess and self.response.getCGIHeader('Location') != None:
			self.requestNumber = self.requestNumber + 1
			# CGI local redirect response (RFC 6.2.2)
			self.parseURI(self.response.getCGIHeader('Location'))
			self.determineFilepath()
			# check for too many recursions
			if self.requestNumber > self.config.configurations['cgirecursionlimit']:
				self.setInternalServerError('Recursion in CGI script')
				return False
			return True
		else:
			return False


	# parses the headers of the CGI script 
	# returns the pair (success,cgiBody)
	def parseCGIHeaders(self,document):
		document = document.lstrip()
		cgiBody = ''

		# determine end of line character (RFC says \n, but some implementations do \r\n)
		separator = '\n'
		pos = document.find('\n\n')
		posRN = document.find('\r\n\r\n')
		if pos == -1 or posRN != -1 and pos > posRN:
			pos = posRN
			separator = '\r\n'

		header = document[:pos]
		body = document[pos+len(separator)*2:]
		# parse header
		lines = header.split(separator)
		for line in lines:
			line = line.strip()
			line = re.sub('\s{2,}', ' ', line)
			pos = line.find(':')
			if pos <= 0 or pos >= len(line)-1:
				self.sendError(500,'Bad Header in CGI response')
				return (False,'')
			key = line[0:pos].strip()
			value = line[pos+1:len(line)].strip()
			self.response.setCGIHeader(key,value)

		if len(self.response.cgiHeaders) == 0:
			self.sendError(500,'CGI Script has no headers')
			return (False,'')

		location = self.response.getCGIHeader('Location')
		if location == None:
			# document response (RFC: 6.2.1)
			if body != None and body != '':
				if self.response.getCGIHeader('Content-Type') == None:
					# content-type must be specified
					self.sendError(500,'CGI Script must specify content type')
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
					newEnv['REDIRECT_URL'] = self.request.filepath[len(self.config.virtualHosts[self.request.virtualHost]['documentroot']):] + self.request.cgiPathInfo
				else:
					newEnv['REDIRECT_URL'] = self.request.filepath[len(self.config.virtualHosts[self.request.virtualHost]['documentroot']):]
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
						self.sendError(500,'CGI Script must specify content type')
						return (False,'')
					# success
					cgiBody = body

		return (True,cgiBody)


# This class provides an execution environment to the CGI script, which monitors the time it takes and aborts the script if it takes too long
class CGIExecutor():

	def __init__ (self, request):
		# Script process
		self.process = None
		# HttpRequest object
		self.request = request


	# executes the CGI script in a thread, which creates a new process that executes the requested scriptfile
	# the thread will cause the process to terminate after a timeout
	def execute (self):
		
		# executed in a separate thread
		def cgiThread():
			args = [self.request.request.filepath]
			if self.request.request.cgiExecutor != None:
				# use executor to run script
				args = [self.request.request.cgiExecutor,self.request.request.filepath]

			# creates a new process, running the script
			try:
			        self.process = subprocess.Popen(args,stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE,env=self.request.request.cgiEnv)

				# eventual POST data goes to stdin
				if self.request.request.body != '':
					self.process.stdin.write(self.request.request.body)

				# fetch response blockwise and flush to listener
				err = 'init'
				out = self.process.stdout.read(self.request.config.configurations['socketbuffersize'])
				errorData = ''
				tmp = ''
				headerParsed = False
				success = True
				while err != '' or out != '':
					nextOut = self.process.stdout.read(self.request.config.configurations['socketbuffersize'])
					err = self.process.stderr.read(self.request.config.configurations['socketbuffersize'])
					errorData = errorData + err

					if not headerParsed:
						tmp = tmp + out
						m = re.match(r'((.+)(\r\n\r\n|\n\n))(.*)',tmp,re.DOTALL)
						if m != None:
							headerParsed = True
							success, cgiBody = self.request.parseCGIHeaders(tmp)
							if success:
								self.request.generateResponseHeaderMessage()
								self.request.appendResponseMessageBody(cgiBody)
								self.request.flushResponseToListener(nextOut == '')
					else:
						if success:
							self.request.appendResponseMessageBody(out)
							self.request.flushResponseToListener(nextOut == '')

					out = nextOut

				if not self.request.response.flushed:
					self.request.sendError(500,'Syntax Error in CGI Response')

				# if some data is available on standarderror, log to errorlog
				if errorData.strip() != '':
					self.request.logError(errorData.replace('\n','').strip())
			except:
				pass

		thread = threading.Thread(target=cgiThread)
		thread.start()
		thread.join(self.request.config.configurations['cgitimeout'])
		# if thread is still alive after timeout means that the script took to long
		if thread.is_alive():
			self.process.terminate()
			thread.join()
			return -1

		return 0


class OutputFilterProcessor:

	def __init__(self, request):
		self.request = request
		self.message = ''
		self.outputFilterDirectory = None
		self.currentFilter = None
		self.process = None


	def getBody(self):
		pos = self.message.find('\r\n\r\n')
		if pos == -1:
			return ''
		else:
			return self.message[pos+4:]

	def setBody(self, body):
		pos = self.message.find('\r\n\r\n')
		if pos == -1:
			return
		else:
			self.message = self.message[:pos+4] + body

	def execute(self):
		if self.request.response.statusCode >= 400 or self.outputFilterDirectory == None:
			return True
		
		def runFilter():
			try:
				script = self.request.config.virtualHosts[self.request.request.virtualHost]['extfilterdefine'][self.currentFilter]
				self.process = subprocess.Popen(script,stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
				# response body goes to stdin
				self.process.stdin.write(self.getBody())
				# the response is on standardoutput
				body, errorData = self.process.communicate()
				self.setBody(body)
				# if some data is available on standarderror, log to errorlog
				if errorData != None and errorData != '':
					self.request.logError(errorData.replace('\n',''))
			except:
				self.request.sendError(500,'Error executing filter '+self.currentFilter)

		if self.request.response.connectionClose:
			self.message = self.message + self.request.response.message
			# all data received
			# run one filter after the other
			for f in self.request.config.virtualHosts[self.request.request.virtualHost]['directory'][self.outputFilterDirectory]['setoutputfilter']:
				self.currentFilter = f
				thread = threading.Thread(target=runFilter)
				thread.start()
				thread.join(self.request.config.configurations['cgitimeout'])
				# if thread is still alive after timeout means that the script took to long
				if thread.is_alive():
					self.process.terminate()
					thread.join()
					self.request.sendError(500,'Filter aborted because of timeout '+self.currentFilter)

				if self.request.response.statusCode >= 400:
					# break if an error occurred
					return False

			self.request.response.message = self.message
			return True
		else:
			# more data to receive
			self.message = self.message + self.request.response.message
			return False

