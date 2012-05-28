#!/usr/bin/python
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from os import path, curdir, sep

# privilege separation
# next meeting end of may
class MyHandler(BaseHTTPRequestHandler):

	documentroot = '/home/stefan/python/docs'

	def do_GET(self):
		try:
			resource = path.abspath(self.documentroot + sep + self.path)
			if resource.startswith(self.documentroot):
				f = open (resource)
				self.send_response(200)
				self.send_header('Content-type','text/html')
				self.end_headers()
				self.wfile.write(f.read())
				f.close()
			else:
				self.send_error(403,'Forbidden %s' % self.path)
			return
		except IOError:
			self.send_error(404,'File Not Found %s' % self.path)

	

def main():
	try:
		server = HTTPServer(('',85), MyHandler)
		print 'Server started'
		server.serve_forever()
	except KeyboardInterrupt:
		print 'Server stopped'
		server.socket.close()

if __name__ == '__main__':
	main()
