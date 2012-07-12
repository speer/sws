import os, pwd, grp
from os import path, sep
import logging

class ErrorFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.ERROR or record.levelno == logging.WARN

class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO


class SwsConfiguration:

	MAIN_CONFIG_FILE = 'sws.conf'
	SITES_ENABLED_FOLDER = 'sites-enabled'

	def __init__(self, configFolder):
		self.configFolder = path.abspath(configFolder)
		self.configFile = path.abspath(self.configFolder + sep + SwsConfiguration.MAIN_CONFIG_FILE)
		self.configurations = {
			'listen':80,
			'host':'',
			'pidfile':None,
			'communicationsocketfile':None,
			'user':None,
			'group':None,
			'hostnamelookups':False,
			'defaulttype':None,
			'cgitimeout':30,
			'cgirecursionlimit':10,
			'listenqueuesize':10,
			'socketbuffersize':8192,
			'errordocumentroot':None,
			'errordocument':{
				403:{'msg':'Forbidden','defaulttxt':'Status 403 - Forbidden. You are not allowed to access this resource.','file':None},
				404:{'msg':'Not Found','defaulttxt':'Status 404 - File Not Found','file':None},
				500:{'msg':'Internal Server Error','defaulttxt':'Status 500 - Internal Server Error','file':None}
			},
			'errorlogfile':None,
			'accesslogfile':None
		}
		self.virtualHosts = {}
		self.defaultVirtualHost = None
		logging.getLogger('sws').setLevel(logging.CRITICAL)

	def readConfigFile(self, configFile):
		configLines = ''
		try:
			f = open (configFile,'r')
			line = 'init'
			while line != '':
				line = f.readline()
				if line.strip().startswith('#') or line.strip() == '':
					continue
				configLines = configLines + line
			return (True, configLines)
		except:
			return (False, 'Cannot read configuration file '+configFile)

	def initLogger(self, name, errorFile, accessFile):
		logger = logging.getLogger(name)
		logger.setLevel(logging.INFO)

		errorHandler = logging.FileHandler(errorFile)
		errorHandler.addFilter(ErrorFilter())
		errorFormatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
		errorHandler.setFormatter(errorFormatter)

		accessHandler = logging.FileHandler(accessFile)
		accessHandler.addFilter(InfoFilter())
		accessFormatter = logging.Formatter('[%(asctime)s] %(message)s')
		accessHandler.setFormatter(accessFormatter)

		logger.addHandler(errorHandler)
		logger.addHandler(accessHandler)


	def initVHost (self, vHost):
		errorDocs = {}
		for err in self.configurations['errordocument'].keys():
			errorDocs[err] = self.configurations['errordocument'][err]['file']

		self.virtualHosts[vHost] = {
			'serveradmin':'',
			'servername':None,
			'serveralias':[],
			'documentroot':None,
			'cgiroot':[],
			'directoryindex':[],
			'errorlogfile':self.configurations['errorlogfile'],
			'accesslogfile':self.configurations['accesslogfile'],
			'errordocumentroot':self.configurations['errordocumentroot'],
			'errordocument':errorDocs
		}


	def parseFile(self):

		# parse main config file

		if not os.path.isdir(self.configFolder):
			return (False, 'Configuration folder '+self.configFolder+' not found')
		if not os.path.isfile(self.configFile):
			return (False, 'Configuration file '+self.configFile+' not found')

		success, configLines = self.readConfigFile(self.configFile)
		if not success:
			return (False,configLines)

		lines = configLines.splitlines()
		for line in lines:
			fields = line.split()

			if len(fields) < 2:
				return (False, 'Syntax error in configuration directive: '+line)

			directive = fields[0].lower()

			if directive not in self.configurations.keys():
				return (False, 'Unknown configuration directive: '+line)

			if directive in ['errordocument'] and len(fields) != 3:
				return (False, 'Syntax error in configuration directive: '+line)

			if directive not in ['errordocument'] and len(fields) != 2:
				return (False, 'Syntax error in configuration directive: '+line)

			# integer directives
			if directive in ['listen','cgitimeout','listenqueuesize','socketbuffersize','cgirecursionlimit']:
				try:
					value = int(fields[1])
					self.configurations[directive] = value
					continue
				except:
					return (False, 'Type error in configuration directive: '+line)

			# boolean directives
			if directive in ['hostnamelookups']:
				if fields[1].lower() == 'on':
					self.configurations[directive] = True
				elif fields[1].lower() == 'off':
					self.configurations[directive] = False
				else:
					return (False, 'Type error in configuration directive: '+line)
				continue

			# errordocument
			if directive in ['errordocument']:
				code = -1
				try:
					code = int(fields[1])
				except:
					return (False, 'Type error in code of errordocument directive: '+line)
				if not code in self.configurations[directive].keys():
					return (False, 'Error code not supported by server: '+line)
				self.configurations['errordocument'][code]['file'] = fields[2]
				continue
	
			# file
			if directive in ['communicationsocketfile','pidfile','errorlogfile','accesslogfile']:
				filepath = os.path.abspath(fields[1])
				pos = filepath.rfind(sep)
				if not os.path.isdir(filepath[:pos]):
					return (False, 'Folder does not exist: '+filepath[:pos])
				self.configurations[directive] = filepath
				continue
	
			# directory
			if directive in ['errordocumentroot']:
				if not os.path.isdir(os.path.abspath(fields[1])):
					return (False, 'Folder does not exist: '+line)
				self.configurations[directive] = os.path.abspath(fields[1])
				continue
	
			# user
			if directive in ['user']:
				try:
					pw = pwd.getpwnam(fields[1])
					self.configurations[directive] = int(pw.pw_uid)
				except:
					try:
						pw = pwd.getpwuid(int(fields[1]))
						self.configurations[directive] = int(pw.pw_uid)
					except:
						return (False, 'User does not exist: '+line)
				continue

			# group
			if directive in ['group']:
				try:
					gr = grp.getgrnam(fields[1])
					self.configurations[directive] = int(gr.gr_gid)
				except:
					try:
						gr = grp.getgrgid(int(fields[1]))
						self.configurations[directive] = int(gr.gr_gid)
					except:
						return (False, 'Group does not exist: '+line)
				continue

			# string directive
			self.configurations[directive] = fields[1]
	
		for directive in self.configurations.keys():
			if self.configurations[directive] == None:
				return (False, 'Mandatory directive not specified: '+directive)


		# init main logger
		logging.getLogger('sws').setLevel(logging.INFO)
		self.initLogger('sws',self.configurations['errorlogfile'],self.configurations['accesslogfile'])

		# parse virtualhosts

		# check if sites enabled folder exists
		sitesEnabled = os.path.abspath(self.configFolder + sep + SwsConfiguration.SITES_ENABLED_FOLDER)
		if not os.path.isdir(sitesEnabled):
			return (False, 'Folder does not exists: '+sitesEnabled)
	
	
		for filename in os.listdir(sitesEnabled):
			vHost = os.path.abspath(sitesEnabled + sep + filename)
			# skip directories
			if not os.path.isfile(vHost) or not vHost.endswith('.conf'):
				continue
	
			success, configLines = self.readConfigFile(vHost)
			if not success:
				return (False,configLines)
	
			self.initVHost(vHost)
			lines = configLines.splitlines()
			for line in lines:
				fields = line.split()
	
				if len(fields) < 1:
					return (False, 'Syntax error in configuration directive: '+line)
	
				directive = fields[0].lower()

				# defaultvirtualhost
				if directive in ['defaultvirtualhost']:
					if self.defaultVirtualHost == None:
						self.defaultVirtualHost = vHost
						continue
					else:
						return (False,'Multiple Default VirtualHosts')

				if directive not in self.virtualHosts[vHost].keys():
					return (False, 'Unknown configuration directive: '+line)

				if len(fields) < 2:
					return (False, 'Syntax error in configuration directive: '+line)

				if directive in ['errordocument'] and len(fields) != 3:
					return (False, 'Syntax error in configuration directive: '+line)

				if directive not in ['errordocument','directoryindex','serveralias','cgiroot'] and len(fields) != 2:
					return (False, 'Syntax error in configuration directive: '+line)

				# multiple values
				if directive in ['directoryindex','serveralias','cgiroot']:
					first = False
					for field in fields:
						if not first:
							first = True
							continue
						self.virtualHosts[vHost][directive].append(field)
					continue

				# directory
				if directive in ['documentroot','errordocumentroot']:
					if not os.path.isdir(os.path.abspath(fields[1])):
						return (False, 'Folder does not exist: '+line)
					self.virtualHosts[vHost][directive] = os.path.abspath(fields[1])
					continue

				# errordocument
				if directive in ['errordocument']:
					code = -1
					try:
						code = int(fields[1])
					except:
						return (False, 'Type error in code of errordocument directive: '+line)
					if not code in self.configurations[directive].keys():
						return (False, 'Error code not supported by server: '+line)
					self.virtualHosts[vHost]['errordocument'][code] = fields[2]
					continue

				# file
				if directive in ['errorlogfile','accesslogfile']:
					filepath = os.path.abspath(fields[1])
					pos = filepath.rfind(sep)
					if not os.path.isdir(filepath[:pos]):
						return (False, 'Folder does not exist: '+filepath[:pos])
					self.virtualHosts[vHost][directive] = filepath
					continue

				# string directive
				self.virtualHosts[vHost][directive] = fields[1]


		if len(self.virtualHosts) == 0:
			return (False, 'No VirtualHost specified')

		if self.defaultVirtualHost == None:
			return (False, 'No DefaultVirtualHost specified')


		# check for mandatory directives
		for vHost in self.virtualHosts.keys():	
			# set logger
			self.initLogger(vHost,self.virtualHosts[vHost]['errorlogfile'],self.virtualHosts[vHost]['accesslogfile'])

		# check for mandatory directives
		for vHost in self.virtualHosts.keys():
			for directive in self.virtualHosts[vHost].keys():
				if self.virtualHosts[vHost][directive] == None:
					return (False, 'Mandatory directive ('+directive+') not specified in VirtualHost: '+vHost)

		return (True,'Parsing OK')


#c = SwsConfiguration ('/home/stefan/sws/config')
#print c.parseFile()[1]
