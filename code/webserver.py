#!/usr/bin/python
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import os
from os import path, sep, stat
from multiprocessing import Process
import subprocess

class MyHandler(BaseHTTPRequestHandler):

	documentroot = '/home/stefan/sws/docs'
	cgiroot = 'cgi-bin'

	def getFileContent(self,filename):
		f = open(filename)
		return f.read()

	def executeCGI(self,filename):
		if os.access(filename, os.X_OK):
			p = subprocess.Popen([filename],stdout=subprocess.PIPE)
			return p.communicate()[0]
		else:
			raise IOError
		

	def prochandler(self,resource):
		try:
			print 'Process', os.getpid(), ', Uid:',os.getuid(),', Gid:',os.getgid()
			st = os.stat(resource)
			os.setgid(st.st_gid)
			os.setuid(st.st_uid)
			print 'Process', os.getpid(), ', Uid:',os.getuid(),', Gid:',os.getgid()
			responseBody = ''
			if resource.startswith(self.documentroot + sep + self.cgiroot):
				responseBody = self.executeCGI(resource)
			else:
				responseBody = self.getFileContent(resource)
			self.send_response(200)
			self.send_header('Content-type','text/html')
			self.end_headers()
			self.wfile.write(responseBody)
		except:
			self.send_error(500,'Internal Server Error')


	def do_GET(self):
		resource = path.abspath(self.documentroot + sep + self.path)
		if resource.startswith(self.documentroot):
			if (os.path.isfile(resource)):
				p = Process(target=self.prochandler, args=(resource,))
				p.start()
				p.join()
			else:
				self.send_error(404,'File Not Found %s' % self.path)
		else:
			self.send_error(403,'Forbidden %s' % self.path)
		return



def main():
	try:
		server = HTTPServer(('',80), MyHandler)
		print 'Server started'
		server.serve_forever()
	except KeyboardInterrupt:
		print 'Server stopped'
		server.socket.close()

if __name__ == '__main__':
	main()
