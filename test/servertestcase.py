#!/usr/bin/python -B

import unittest
import sys
sys.path.append('../code')
import config
import httplib

class ServerTestCase (unittest.TestCase):

	PORT = 81
	METHODS = ['GET','POST','HEAD']

	def testLocalhost(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/')
			response = connection.getresponse()
			assert response.status == 200
			data = response.read()
			data = data.strip()
			if method == 'HEAD':
				assert data == ''
			else:
				assert data == 'success'
			connection.close()

	def testLocalhostForbidden(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			# break out of documentroot
			connection.request(method,'../127.0.0.1/index.html')
			response = connection.getresponse()
			assert response.status == 403
			connection.close()


	def testLocalhostNotFound(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			# try to access not existing file
			connection.request(method,'index_notfound.html')
			response = connection.getresponse()
			assert response.status == 404
			connection.close()


	def testLocalhostMethodNotSupported(self):
		connection = httplib.HTTPConnection('localhost', self.PORT)
		connection.connect()
		# try invalid request method
		connection.request('NOTSUPPORTED','/')
		response = connection.getresponse()
		assert response.status == 400
		connection.close()


	def testLocalhostRequestBody(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/','variable=100',{'myheader':123})
			response = connection.getresponse()
			assert response.status == 200
			connection.close()


	def testLocalhostCGIExecutor(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			# owner of the file must be set to stefan
			connection.request(method,'/cgi-bin/executor.sh')
			response = connection.getresponse()
			assert response.status == 200
			data = response.read()
			data = data.strip()
			if method == 'HEAD':
				assert data == ''
			else:
				assert data == 'stefan'
			connection.close()


	def test127001CGIExecutor(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('127.0.0.1', self.PORT)
			connection.connect()
			# owner of the file must be set to www-data
			connection.request(method,'/cgi-bin/executor.sh')
			response = connection.getresponse()
			assert response.status == 200
			data = response.read()
			data = data.strip()
			if method == 'HEAD':
				assert data == ''
			else:
				assert data == 'www-data'
			connection.close()


	def testLocalhostRequestBodyCGI(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/cgi-bin/post.pl?v2=200','v1=100')
			response = connection.getresponse()
			data = response.read()
			data = data.strip()
			assert response.status == 200

			if method == 'HEAD':
				assert data == ''
			elif method == 'POST':
				assert data == 'v1 => 100'
			else:
				assert data == 'v2 => 200'
			connection.close()

	
	def testLocalhostRequestBodyCGIPHP(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/cgi-bin/php?v1=4','v2=5',{'content-type':'application/x-www-form-urlencoded'})
			response = connection.getresponse()
			data = response.read()
			data = data.strip()
			assert response.status == 200
			if method == 'HEAD':
				assert data == ''
			elif method == 'POST':
				assert data == '9'
			else:
				assert data == '4'
			connection.close()

	def testLocalhostCGIRedirect1(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			# redirect to 127.0.0.1
			connection.request(method,'/cgi-bin/loc.pl')
			response = connection.getresponse()
			assert response.status == 302
			assert response.getheader('Location') == 'http://127.0.0.1:81/'
			connection.close()

	def testLocalhostCGIRedirect2(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			# redirect to /
			connection.request(method,'/cgi-bin/loc2.pl')
			response = connection.getresponse()
			assert response.status == 200
			data = response.read()
			data = data.strip()
			if method == 'HEAD':
				assert data == ''
			else:
				assert data == 'success'
			connection.close()

	def testLocalhostCGIRedirect3(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			# redirect to itself -> recursion
			connection.request(method,'/cgi-bin/loc3.pl')
			response = connection.getresponse()
			assert response.status == 500
			connection.close()


	def testLocalhostCGIForever(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			# endless script -> abort (CGITimeout in configuration set to 1 sek)
			connection.request(method,'/cgi-bin/forever.sh')
			response = connection.getresponse()
			assert response.status == 500
			connection.close()


	def testLocalhostCGIByRootNoAccess(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			# script owned by root and no access privileges for default user
			connection.request(method,'/cgi-bin/env.pl')
			response = connection.getresponse()
			assert response.status == 500
			connection.close()

	def testLocalhostCGIByRootAccess(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			# script owned by root and access privileges for default user (stefan)
			connection.request(method,'/cgi-bin/executor2.sh')
			response = connection.getresponse()
			assert response.status == 200
			data = response.read()
			data = data.strip()
			if method == 'HEAD':
				assert data == ''
			else:
				assert data == 'stefan'
			connection.close()


	def testLocalhostCGINotExecutable(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			# script is not executable
			connection.request(method,'/cgi-bin/notexecutable.pl')
			response = connection.getresponse()
			assert response.status == 500
			connection.close()


	def testLocalhostCGIBadHeader(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/cgi-bin/badheader.pl')
			response = connection.getresponse()
			assert response.status == 500
			connection.close()


	def testLocalhostCGINoContentType(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/cgi-bin/nocontenttype.pl')
			response = connection.getresponse()
			assert response.status == 500
			connection.close()


	def testLocalhostCGINoCGI(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/cgi-bin/notcgi.html')
			response = connection.getresponse()
			assert response.status == 200
			data = response.read()
			data = data.strip()
			if method == 'HEAD':
				assert data == ''
			else:
				assert data == 'successnotcgi'
			connection.close()

	def testLocalhostFilter(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/filter/index.html')
			response = connection.getresponse()
			assert response.status == 200
			assert response.getheader('content-encoding') == 'gzip'
			connection.close()

	def testLocalhostEndlessFilter(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/filter2/index.html')
			response = connection.getresponse()
			assert response.status == 500
			connection.close()

	def testLocalhostFilterFileNotFound(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/filter2/index2.html')
			response = connection.getresponse()
			assert response.status == 404
			connection.close()

	def testLocalhostFilterScriptNotFound(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/filter3/index.html')
			response = connection.getresponse()
			assert response.status == 500
			connection.close()

	def testLocalhostFiltered(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/filter4/index.html')
			response = connection.getresponse()
			assert response.status == 200
			data = response.read()
			data = data.strip()
			if method == 'HEAD':
				assert data == ''
			else:
				assert data == 'filtered'
			connection.close()

	def testLocalhostFilterNotExecutable(self):
		for method in self.METHODS:
			connection = httplib.HTTPConnection('localhost', self.PORT)
			connection.connect()
			connection.request(method,'/filter5/index.html')
			response = connection.getresponse()
			assert response.status == 500
			connection.close()

if __name__ == "__main__":
	unittest.main()

