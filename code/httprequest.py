import re
import os
from os import path, sep, stat
from time import gmtime, strftime
import subprocess

# not python standard lib - for mime type detection
import magic

# redirect response cgi scripts (Location header)

# not parse request twice -> serializable
# cgi fields finishing, since request

class Request:

	def __init__ (self):
		self.headers = {}
		# method (GET, HEAD, POST)
		self.method = None
		self.uri = None
		self.filepath = ''
		self.host = None
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
		self.statusCode = None
		self.statusMessage = None
		self.body = None
		self.message = ''

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
		self.statusCode = errorCode
		self.statusMessage = errorMessage
		self.body = errorDocument


class HttpRequest:

	SERVER_NAME = 'SWS/0.1'
	SERVER_ADMIN = 'stefan@peerweb.it'
	DOCUMENT_ROOT = '/home/stefan/sws/docs'
	CGI_ROOT = 'cgi-bin'
	DIRECTORY_INDEX = ['index.html','index.php','home.html']

	CONNECTION_TYPE = 'close'
	CGI_PROTOCOL = 'CGI/1.1'
	HTTP_PROTOCOL = 'HTTP/1.1'
	ACCEPTED_PROTOCOLS = ['HTTP/1.0','HTTP/1.1']
	ACCEPTED_REQUEST_TYPES = ['GET','HEAD','POST']

        def __init__ (self, connection):
		self.connection = connection
		self.request = Request()
		self.response = Response()


	def receive(self):
		data = 'init'
		msg = ''
		requestHeader = ''
		requestBody = ''
                # get request line and all header fields
		while data != '':
			data = self.connection.recv(4096)
			msg = msg + data
			m = re.match(r'((.+)\r\n\r\n)(.*)',msg,re.DOTALL)
			if m != None:
				requestHeader = m.group(1)
				requestBody = m.group(3)
				# continue reading of the body afterwards
				break
	
		requestHeader = requestHeader.lstrip()
		lines = requestHeader.split('\r\n')
		first = True
		for line in lines:
			line = line.strip()
			line = re.sub('\s{2,}', ' ', line)
			if first:
				# request line
				words = line.split(' ')
				if len(words) != 3:
					self.response.setError(400,'Bad Request','Status 400 - Bad Request Line')
					return
				if words[0].upper() not in HttpRequest.ACCEPTED_REQUEST_TYPES:
					self.response.setError(400,'Bad Request','Status 400 - Command not supported')
					return
				if words[2].upper() not in HttpRequest.ACCEPTED_PROTOCOLS:
					self.response.setError(400,'Bad Request','Status 400 - Version not supported')
					return
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
					return
				key = line[0:pos].strip()
				value = line[pos+1:len(line)].strip()
				self.request.setHeader(key,value)

		# determine host
		if self.request.host == None:
			h = self.request.getHeader('host')
			if h != None and h != '':
				m = re.match(r'([\w\-\.]+)(:(\d+))?',h)
				self.request.host = m.group(1)
			else:
				self.response.setError(400,'Bad Request','Status 400 - No Host specified')
				return
		
		# check if POST message has a message body
		contentLength = self.request.getContentLength()
		if self.request.method == 'POST' and contentLength > 0:
			data = 'init'
		        # get request body
			while len(requestBody) < contentLength and data != '':
				data = self.connection.recv(4096)
				requestBody = requestBody + data
			self.request.body = requestBody
	
		self.response.statusCode = 200
		self.response.statusMessage = 'OK'
		self.response.body = ''
		self.request.message = requestHeader + self.request.body
		self.request.filepath = path.abspath(HttpRequest.DOCUMENT_ROOT + sep + self.request.uri)


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
		cgiEnv = {}
		contentLength = self.request.getContentLength()
		if contentLength > 0:
			cgiEnv['CONTENT_LENGTH'] = str(contentLength)

		contentType = self.request.getHeader('Content-Type')
		if contentType != None:
			cgiEnv['CONTENT_TYPE'] = contentType
	
		cgiEnv['GATEWAY_INTERFACE'] = HttpRequest.CGI_PROTOCOL
#		cgiEnv['PATH_INFO'] = ''
#		cgiEnv['PATH_TRANSLATED'] = ''
		cgiEnv['QUERY_STRING'] = self.request.query
#		cgiEnv['REMOTE_ADDR'] = ''
#		cgiEnv['REMOTE_HOST'] = ''
		cgiEnv['REQUEST_METHOD'] = self.request.method
#		cgiEnv['SCRIPT_NAME'] = ''
		cgiEnv['SERVER_NAME'] = self.request.host
#		cgiEnv['SERVER_PORT'] = ''
		cgiEnv['SERVER_PROTOCOL'] = HttpRequest.HTTP_PROTOCOL
		cgiEnv['SERVER_SOFTWARE'] = HttpRequest.SERVER_NAME
		cgiEnv['DOCUMENT_ROOT'] = HttpRequest.DOCUMENT_ROOT
		cgiEnv['SERVER_ADMIN'] = HttpRequest.SERVER_ADMIN
		cgiEnv['SCRIPT_FILENAME'] = self.request.filepath
		cgiEnv['REQUEST_URI'] = self.request.uri
#		cgiEnv['REMOTE_PORT'] = ''
#		cgiEnv['PATH'] = ''
		
		# http header to environment variable
		for keys in self.request.headers.keys():
			cgiEnv['HTTP_'+keys.replace('-','_').upper()] = self.request.headers[keys]

		return cgiEnv
			

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


	def checkValidity(self):
		if self.response.statusCode == 200:
			return True
		return False

	def sendResponse(self):
		self.connection.send(self.response.message)
		self.connection.close()


	def process (self, removePrivileges=True):
		# check directoryIndex if path is a directory
		if os.path.isdir(self.request.filepath):
			for index in HttpRequest.DIRECTORY_INDEX:
				f = path.abspath (self.request.filepath + sep + index)
				if os.path.isfile(f):
					self.request.filepath = f
					break

		# check if resource is inside the documentroot (jail)
		if self.request.filepath.startswith(HttpRequest.DOCUMENT_ROOT):
			# check if resource is a valid file
			if os.path.isfile(self.request.filepath):
				try:
					if removePrivileges:
						# check owner of the file
						st = os.stat(self.request.filepath)
						# remove privileges
						os.setgid(st.st_gid)
						os.setuid(st.st_uid)

					# check if resource is a cgi script
					if self.request.filepath.startswith(HttpRequest.DOCUMENT_ROOT + sep + HttpRequest.CGI_ROOT):
						self.processCGIresponse(self.executeCGI())
					else:
						self.response.body = self.getFileContent()

				except Exception:
					self.response.setError(500,'Internal Server Error','Status 500 - Internal Server Error')
			else:
				self.response.setError(404,'File Not Found','Status 404 - The file could not be found')
		else:
			self.response.setError(403,'Forbidden','Status 403 - Forbidden')


	def processCGIresponse(self,document):
		document = document.lstrip()
		m = re.match(r'((.+)\n\n)(.*)',document,re.DOTALL)
		if m != None:
			header = m.group(2)
			body = m.group(3)
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

			if self.response.getCGIHeader('Location') == None:
				# document response (RFC: 6.2.1)

				if self.response.getCGIHeader('Content-Type') == None:
					# clear all cgi headers
					self.response.cgiHeader = {}
					# content-type must be specified
					self.response.setError(500,'Internal Server Error','Status 500 - CGI Script must specify content type')
					return

				# check for status header field
				if self.response.getCGIHeader('Status') != None:
					s = re.match(r'(\d+) (.*)',self.response.getCGIHeader('Status'),re.DOTALL)
					if s != None:
						self.response.statusCode = int(s.group(1))
						self.response.statusMessage = s.group(2)

				self.response.body = body
			else:
				# TODO: redirect response (RFC 6.2.2, 6.2.3, 6.2.4)
				pass
	
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
		cgiEnv = self.generateCGIEnvironment()
		stdinput = None
		if self.request.body != '':
			stdinput = self.request.body
                p = subprocess.Popen([self.request.filepath],stdout=subprocess.PIPE,stdin=stdinput,env=cgiEnv)
		return p.communicate()[0]


