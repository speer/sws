import re
import os
from os import path, sep, stat
from time import gmtime, strftime

# not python standard lib - for mime type detection
import magic


# GET request query parsing?
# CGI script execution: set environment variables according to RFC
# POST request, parse body

# transfer-encoding????


class RequestProcessor:

	def __init__(self, request):
		self.request = request
		self.documentroot = '/home/stefan/sws/docs'
		self.cgiroot = 'cgi-bin'
		self.directoryIndex = ['index.html','index.php','home.html']
		self.resource = path.abspath(self.documentroot + sep + request.path)

	def processRequest (self, removePrivileges=True):

		# check directoryIndex if path is a directory
		if os.path.isdir(self.resource):
			for index in self.directoryIndex:
				f = path.abspath (self.resource + sep + index)
				if os.path.isfile(f):
					self.resource = f
					break

		# check if resource is inside the documentroot (jail)
		if self.resource.startswith(self.documentroot):
			# check if resource is a valid file
			if os.path.isfile(self.resource):
				try:
					if removePrivileges:
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

				except Exception:
					self.request.setResponseError(500,'Internal Server Error','500: Internal Server Error')
			else:
				self.request.setResponseError(404,'File Not Found','404: The file could not be found')
		else:
			self.request.setResponseError(403,'Forbidden','403: Forbidden')

	def getFileContent(self):
		f = open(self.resource)
		content = f.read()
		f.close()
		return content

	def executeCGI(self):
		# check whether resource is an executable file
        	if not os.access(self.resource, os.X_OK):
			raise IOError
		# check if resource is not owned by root
		elif os.getuid() == 0:
			raise Exception
		else:
                	p = subprocess.Popen([self.resource],stdout=subprocess.PIPE)
			return p.communicate()[0]


class HttpRequest:

	# keepalive not supported by the server
	CONNECTION_TYPE = 'close'
	HTTP_VERSION = '1.1'

        def __init__ (self, connection):
		# request fields
		self.connection = connection
		self.command = None
		self.path = None
		self.host = None
		self.protocolVersion = 'HTTP/' + HttpRequest.HTTP_VERSION
		self.headers = {}
		self.requestMessage = ''
		# response fields
		self.responseMessage = ''
		self.statusCode = None
		self.statusMessage = None
		self.document = None
		self.responseHeaders = {}

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
				self.parseURI(words[1])
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

		# determine host
		if self.host == None:
			self.host = self.getHeader('host')


		# check if POST message has a message body
		entityBody = ''
		if self.command == 'POST':
			contentLength = self.getHeader('content-length')
			if contentLength != None and contentLength != 0:
				data = ''
		        	# get request body
				#while not entityBody.endswith('\r\n\r\n'):
				#	data = self.connection.recv(4096)
				#	entityBody = entityBody + data

		self.statusCode = 200
		self.statusMessage = 'OK'
		self.document = ''
		self.requestMessage = msg + entityBody


	def parseURI(self,uri):
		if re.match('[hH][tT][tT][pP][sS]?://',uri) == None:
			# absolute path - host determined afterwards
			m = re.match(r'([^\?]*)(\?(.*))?',uri)
			if m != None:
				self.path = m.group(1)
				self.query = m.group(3)
		else:
			# absolute uri / determines host
			m = re.match(r'[hH][tT][tT][pP]([sS])?://([\w\-\.]+)(:\d+)?([^\?]*)(\?(.*))?',uri)
			if m != None:
				self.host = m.group(2)
				self.path = m.group(4)
				self.query = m.group(6)
			print self.host
			print self.query
			print self.path


	def getHeader(self,searchKey):
		for key in self.headers.keys():
			if key.lower() == searchKey.lower():
				return self.headers[key]
		return None


	def setResponseError(self, errorCode, errorMessage, errorDocument):
		self.statusCode = errorCode
		self.statusMessage = errorMessage
		self.document = errorDocument


	def getContentType(self):
		try:
			mime = magic.Magic(mime=True)
			mime_encoding = magic.Magic(mime_encoding=True)
			contentType = mime.from_buffer(self.document)
			charset = mime_encoding.from_buffer(self.document)
			if charset != 'binary':
				return contentType + ';charset=' + charset
			else:
				return contentType
		except Exception:
			return 'application/unknown'

	def generateResponseHeaders(self):
		self.responseHeaders['Connection'] = HttpRequest.CONNECTION_TYPE
		self.responseHeaders['Content-Length'] = str(len(self.document))
		self.responseHeaders['Content-Type'] = self.getContentType()
		self.responseHeaders['Date'] = strftime("%a, %d %b %Y %H:%M:%S GMT", gmtime())
		self.responseHeaders['Server'] = 'SWS/0.1'

	def generateResponseMessage(self):
		# generate response headers
		self.generateResponseHeaders()

		# generate Status line
		m = self.protocolVersion+' '+str(self.statusCode)+' '+self.statusMessage+'\r\n'

		# add headers
		for hKey in self.responseHeaders.keys():
			m = m + hKey + ':' + self.responseHeaders[hKey]+'\r\n'

		self.responseMessage = m + '\r\n'

		# HEAD request must not have a response body
		if self.command != 'HEAD':
			self.responseMessage = self.responseMessage + self.document


	def checkValidity(self):
		if self.statusCode == 200:
			return True
		return False

	def sendResponse(self):
		self.connection.send(self.responseMessage)
		self.connection.close()


