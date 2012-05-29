#!/usr/bin/python
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import os
from os import path, sep, stat
from multiprocessing import Process

class MyHandler(BaseHTTPRequestHandler):

	documentroot = '/home/stefan/sws/docs'

	def prochandler(self,resource):

		try:
			print 'Process', os.getpid(), ', Uid:',os.getuid(),', Gid:',os.getgid()
			st = os.stat(resource)
			os.setgid(st.st_gid)
			os.setuid(st.st_uid)
			print 'Process', os.getpid(), ', Uid:',os.getuid(),', Gid:',os.getgid()
			f = open (resource)
			self.send_response(200)
			self.send_header('Content-type','text/html')
			self.end_headers()
			self.wfile.write(f.read())
			f.close()
		except IOError:
			self.send_error(404,'File Not Found %s' % self.path)


	def do_GET(self):
		resource = path.abspath(self.documentroot + sep + self.path)
		if resource.startswith(self.documentroot):			
			p = Process(target=self.prochandler, args=(resource,))
			p.start()
			p.join()
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
