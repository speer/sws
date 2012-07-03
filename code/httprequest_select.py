import re
import os
from os import path, sep, stat
from time import gmtime, strftime
import subprocess
import cPickle
import socket
import urllib

# not python standard lib - for mime type detection
import magic

class RequestResponseWrapper:

	def __init__ (self, request, response):
		self.request = request
		self.response = response

class Request:

	def __init__ (self):
		self.headers = {}
		self.cgiEnv = {}
		# method (GET, HEAD, POST)
		self.method = None
		self.uri = None
		self.filepath = ''
		self.cgiPathInfo = None
		self.host = None
		self.remoteAddr = None
		self.remoteFqdn = None
		self.remotePort = None
		self.serverPort = None
		self.serverAddr = None
		self.protocol = None
		self.query = ''
		self.body = ''
		self.message = ''

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


class Response:
	
	def __init__ (self):
		self.headers = {}
		self.cgiHeaders = {}
		self.statusCode = 200
		self.statusMessage = 'OK'
		self.body = ''
		self.message = ''
		self.reprocess = False

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

	def setError(self, errorCode, errorMessage, errorDocument):
		self.cgiHeaders = {}
		self.statusCode = errorCode
		self.statusMessage = errorMessage
		self.body = errorDocument


class HttpRequest:

	SOCKET_BUF_SIZE = 4096

	SERVER_NAME = 'SWS/0.1'
	SERVER_ADMIN = 'stefan@peerweb.it'
	DOCUMENT_ROOT = '/home/stefan/sws/docs'
	CGI_ROOT = 'cgi-bin'
	DIRECTORY_INDEX = ['index.html','index.php','home.html','env.pl']

	CONNECTION_TYPE = 'close'
	CGI_PROTOCOL = 'CGI/1.1'
	HTTP_PROTOCOL = 'HTTP/1.1'
	ACCEPTED_PROTOCOLS = ['HTTP/1.0','HTTP/1.1']
	ACCEPTED_REQUEST_TYPES = ['GET','HEAD','POST']
	# enabling this results to poor performance
	FQDN_LOOKUP_ENABLED = False

        def __init__ (self, connection, pickled=False):
		self.connection = connection
		self.tmpData = ''
		self.bytessent = 0
		self.requestHeader = ''
		self.requestBody = ''
		self.headerReceived = False
		if not pickled:
			# read request from connection
			self.request = Request()
			self.response = Response()
			self.request.serverAddr = connection.getsockname()[0]
			self.request.serverPort = connection.getsockname()[1]
			self.request.remoteAddr = connection.getpeername()[0]
			self.request.remotePort = connection.getpeername()[1]
			if HttpRequest.FQDN_LOOKUP_ENABLED:
				self.request.remoteFqdn = socket.getfqdn(self.request.remoteAddr)
			else:
				self.request.remoteFqdn = self.request.remoteAddr
		else:
			# unpickle request and response objects
			self.unpickle()

	def unpickle(self):
		data = 'init'
		msg = ''
		msgLength = -1
		while data != '':
                        data = self.connection.recv(4096)
                        msg = msg + data
			m = re.match(r'(\d+);(.*)',msg,re.DOTALL)
			if m != None and msgLength == -1:
				msgLength = int(m.group(1))
				msg = m.group(2)
			if msgLength <= len(msg):
				# all data received
				break
		wrapper = cPickle.loads(msg)
		self.request = wrapper.request
		self.response = wrapper.response

	# returns true when request was fully received
	def receiveRequest(self):
		if not self.headerReceived:
			# receive request header
			data = self.connection.recv(HttpRequest.SOCKET_BUF_SIZE)
			self.tmpData = self.tmpData + data
			m = re.match(r'((.+)\r\n\r\n)(.*)',self.tmpData,re.DOTALL)
			if m != None:
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

	def checkRequestBodyReceived(self):
		if len(self.requestBody) >= self.request.getContentLength():
			self.request.body = self.requestBody
			self.request.message = self.requestHeader + self.request.body
			return True
		else:
			return False
		

	# when request is fully received: returns true
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
					self.response.setError(400,'Bad Request','Status 400 - Bad Request Line')
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
					self.response.setError(400,'Bad Request','Status 400 - Bad Header')
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
		
		self.request.message = self.requestHeader
		return True
		

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


	def checkValidity(self):
		if self.response.statusCode != 200:
			return False
		if self.request.method not in HttpRequest.ACCEPTED_REQUEST_TYPES:
			self.response.setError(400,'Bad Request','Status 400 - Command not supported')
			return False
		if self.request.protocol not in HttpRequest.ACCEPTED_PROTOCOLS:
			self.response.setError(400,'Bad Request','Status 400 - Version not supported')
			return False
		if self.request.host == None:
			self.response.setError(400,'Bad Request','Status 400 - No Host specified')
			return False
		return True

	def getContentType(self):
		try:
			mime = magic.Magic(mime=True)
			mime_encoding = magic.Magic(mime_encoding=True)
			contentType = mime.from_buffer(self.response.body)
			charset = mime_encoding.from_buffer(self.response.body)
			if charset != 'binary':
				return contentType + ';charset=' + charset
			else:
				return contentType
		except Exception:
			return 'application/octet-stream'

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
		
		# http header to environment variable
		for keys in self.request.headers.keys():
			self.request.cgiEnv['HTTP_'+keys.replace('-','_').upper()] = self.request.headers[keys]


	def generateResponseMessage(self):
		# generate response headers
		self.response.setHeader('Date',strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime()))
		self.response.setHeader('Server',HttpRequest.SERVER_NAME)
		self.response.setHeader('Connection',HttpRequest.CONNECTION_TYPE)
		
		# determine contentlength
		contentLength = len(self.response.body)
		if contentLength > 0:
			self.response.setHeader('Content-Length', str(contentLength))

		# set content-length if not a cgi script
		if len(self.response.cgiHeaders) == 0:
			self.response.setHeader('Content-Type', self.getContentType())
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

		# HEAD request must not have a response body
		if self.request.method != 'HEAD':
			self.response.message = self.response.message + self.response.body


	def sendResponse(self,pickled=False):
		if not pickled:
			if self.bytessent == 0:
				self.tmpData = self.response.message
			byteswritten = self.connection.send(self.tmpData)
			self.bytessent = self.bytessent + byteswritten
			self.tmpData = self.tmpData[byteswritten:]
			return len(self.tmpData) == 0
		else:
			self.connection.send(cPickle.dumps(RequestResponseWrapper(self.request,self.response)))
			return True

	def isJailedInto(self, jail, path):
		return path.startswith(jail + sep) or path == jail


	def process (self):
		# check if resource is inside the documentroot (jail)
		if self.isJailedInto(HttpRequest.DOCUMENT_ROOT, self.request.filepath):

			# check if resource is a cgi script
			if self.isJailedInto(HttpRequest.DOCUMENT_ROOT + sep + HttpRequest.CGI_ROOT, self.request.filepath):
				self.processCGI()
			else:
				self.processDocument()

		else:
			self.response.setError(403,'Forbidden','Status 403 - Forbidden')


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
				self.response.body = self.getFileContent()
			except:
				self.response.setError(500,'Internal Server Error','Status 500 - Internal Server Error')
		else:
			self.response.setError(404,'File Not Found','Status 404 - The file could not be found')



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
			if 1:
		#	try:
				# check owner of the file
				st = os.stat(self.request.filepath)
				# remove privileges
				os.setgid(st.st_gid)
				os.setuid(st.st_uid)
				# check if resource is a cgi script
				self.generateCGIresponse(self.executeCGI())
		#	except:
		#		self.response.setError(500,'Internal Server Error','Status 500 - Internal Server Error')
		else:
			self.response.setError(404,'File Not Found','Status 404 - The file could not be found')



	def generateCGIresponse(self,document):
		document = document.lstrip()
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
					self.response.setError(500,'Internal Server Error','Status 500 - Bad Header in CGI response')
					return
				key = line[0:pos].strip()
				value = line[pos+1:len(line)].strip()
				self.response.setCGIHeader(key,value)

			if len(self.response.cgiHeaders) == 0:
				self.response.setError(500,'Internal Server Error','Status 500 - CGI Script has no headers')

			location = self.response.getCGIHeader('Location')
			if location == None:
				# document response (RFC: 6.2.1)
				if body != None and body != '':
					if self.response.getCGIHeader('Content-Type') == None:
						# content-type must be specified
						self.response.setError(500,'Internal Server Error','Status 500 - CGI Script must specify content type')
						return

					self.response.body = body

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
							self.response.setError(500,'Internal Server Error','Status 500 - CGI Script must specify content type')
							return
						self.response.body = body

		else:
			self.response.setError(500,'Internal Server Error','Status 500 - CGI returned wrong response')
			


	def getFileContent(self):
		f = open(self.request.filepath)
		content = f.read()
		f.close()
		return content


	def executeCGI(self):
		# check whether resource is an executable file
        	if not os.access(self.request.filepath, os.X_OK):
			raise IOError

		# check if resource is owned by someone except root
		st = os.stat(self.request.filepath)
		if st.st_uid == 0:
			raise Exception

		# call cgi script, if there is a body it is provided as input stream, pass environment variables
		self.generateCGIEnvironment()
	        p = subprocess.Popen([self.request.filepath],stdout=subprocess.PIPE,stdin=subprocess.PIPE,env=self.request.cgiEnv)
		if self.request.body != '':
			p.stdin.write(self.request.body)
		return p.communicate()[0]


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
				self.response.setError(500,'Internal Server Error','Status 500 - recursion in CGI script')
				return False
			return True
		else:
			return False

