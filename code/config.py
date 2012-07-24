import os, pwd, grp
from os import path, sep
import logging
import re

# filter classes, that help logging error and access logs into different files
class ErrorFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.ERROR or record.levelno == logging.WARN

class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO

# this class retrieves the servers main log file, parses it and then retrieves all virtualhost configuration files and also parses them.
# additionally it initializes the logger
class SwsConfiguration:

	# name of the main log file
	MAIN_CONFIG_FILE = 'sws.conf'
	# name of the folder, containing a .conf file for each virtualhost
	SITES_ENABLED_FOLDER = 'sites-enabled'

	def __init__(self, configFolder):
		# folder containing the main configuration file and the sites-enabled folder
		self.configFolder = path.abspath(configFolder)
		# path to the configuration file
		self.configFile = path.abspath(self.configFolder + sep + SwsConfiguration.MAIN_CONFIG_FILE)
		# object containing the server configuration
		self.configurations = {
			# port on which the server listens
			'listen':80,
			# address on which the server listens
			'host':'',
			# UNIX socket file for communication between processes
			'communicationsocketfile':None,
			# listener user
			'user':None,
			# listener group
			'group':None,
			# whether the server performs hostname lookups (turn off for performance reasons)
			'hostnamelookups':False,
			# default content type, the server delivers if the content type cannot be determined
			'defaulttype':None,
			# timeout after which cgi scripts get aborted
			'cgitimeout':30,
			# number of consecutive local redirects
			'cgirecursionlimit':10,
			# size of the listen queue for incoming connections
			'listenqueuesize':10,
			# size of the communication buffer
			'socketbuffersize':8192,
			# root for errordocuments
			'errordocumentroot':None,
			# error documents
			'errordocument':{
				403:{'msg':'Forbidden','defaulttxt':'Status 403 - Forbidden. You are not allowed to access this resource.','file':None},
				404:{'msg':'Not Found','defaulttxt':'Status 404 - File Not Found','file':None},
				500:{'msg':'Internal Server Error','defaulttxt':'Status 500 - Internal Server Error','file':None}
			},
			# logfile for error messages
			'errorlogfile':None,
			# logfile for access messages
			'accesslogfile':None,
			# serverside file-extension / content-type associations
			'addtype':{}
		}
		# obejct containing the configurations for every virtualhost
		self.virtualHosts = {}
		# name of the default virtualhost, that is applied if no virtualhost matches a given hostname
		self.defaultVirtualHost = None
		# initialize logger to critical, so that no logging takes place if the log file can not be determined
		logging.getLogger('sws').setLevel(logging.CRITICAL)


	# create a new virtualhost object
	def initVHost (self, vHost):
		# maintain standard errordocuments
		errorDocs = {}
		for err in self.configurations['errordocument'].keys():
			errorDocs[err] = self.configurations['errordocument'][err]['file']

		self.virtualHosts[vHost] = {
			'serveradmin':'',
			'servername':None,
			'serveralias':[],
			'documentroot':None,
			'errorlogfile':self.configurations['errorlogfile'],
			'accesslogfile':self.configurations['accesslogfile'],
			'errordocumentroot':self.configurations['errordocumentroot'],
			'errordocument':errorDocs,
			'directory':{'/':self.initDirectory()},
			'extfilterdefine':{}
		}

	# create a new directory object
	def initDirectory(self):
		return	{
			'directoryindex':[],
			'cgihandler':[],
			'setoutputfilter':[],
			'addheader':{},
			'addtype':{},
			# subfolders should(n't) inherit directive from parent folder
			'stopinheritance':{
				'directoryindex':False,
				'cgihandler':False,
				'setoutputfilter':False,
				'addheader':False,
				'addtype':False
			}
		}


	# get data out of the configuration file
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


	# initialize a logger (either global or optional loggers for every virtualhost)
	def initLogger(self, name, errorFile, accessFile):
		logger = logging.getLogger(name)
		logger.setLevel(logging.INFO)

		errorHandler = logging.FileHandler(errorFile)
		errorHandler.addFilter(ErrorFilter())
		errorFormatter = logging.Formatter('%(message)s')
		errorHandler.setFormatter(errorFormatter)

		accessHandler = logging.FileHandler(accessFile)
		accessHandler.addFilter(InfoFilter())
		accessFormatter = logging.Formatter('%(message)s')
		accessHandler.setFormatter(accessFormatter)

		logger.addHandler(errorHandler)
		logger.addHandler(accessHandler)


	# start the configuration files parsing process
	def parseFile(self):
		# parse main config file

		if not os.path.isdir(self.configFolder):
			return (False, 'Configuration folder '+self.configFolder+' not found',10)
		if not os.path.isfile(self.configFile):
			return (False, 'Configuration file '+self.configFile+' not found',11)

		success, configLines = self.readConfigFile(self.configFile)
		if not success:
			return (False,configLines,12)

		lines = configLines.splitlines()
		for line in lines:

			# check line by line
			line = line.strip()
			fields = line.split()

			if len(fields) < 2:
				return (False, 'Syntax error in configuration directive: '+line,13)

			directive = fields[0].lower()

			if directive not in self.configurations.keys():
				return (False, 'Unknown configuration directive: '+line,14)

			if directive in ['errordocument','addtype'] and len(fields) != 3:
				return (False, 'Syntax error in configuration directive: '+line,15)

			if directive not in ['errordocument','addtype'] and len(fields) != 2:
				return (False, 'Syntax error in configuration directive: '+line,16)

			# integer directives
			if directive in ['listen','cgitimeout','listenqueuesize','socketbuffersize','cgirecursionlimit']:
				try:
					value = int(fields[1])
					if value <= 0:
						return (False, 'Value less or equal to 0 not supported in configuration directive: '+line,43)
					self.configurations[directive] = value
					continue
				except:
					return (False, 'Type error in configuration directive: '+line,17)

			# boolean directives
			if directive in ['hostnamelookups']:
				if fields[1].lower() == 'on':
					self.configurations[directive] = True
				elif fields[1].lower() == 'off':
					self.configurations[directive] = False
				else:
					return (False, 'Type error in configuration directive: '+line,18)
				continue

			# errordocument
			if directive in ['errordocument']:
				code = -1
				try:
					code = int(fields[1])
				except:
					return (False, 'Type error in code of errordocument directive: '+line,19)
				if not code in self.configurations[directive].keys():
					return (False, 'Error code not supported by server: '+line,20)
				self.configurations['errordocument'][code]['file'] = fields[2]
				continue
	
			# file
			if directive in ['communicationsocketfile','errorlogfile','accesslogfile']:
				filepath = os.path.abspath(fields[1])
				pos = filepath.rfind(sep)
				if not os.path.isdir(filepath[:pos]):
					return (False, 'Folder does not exist: '+filepath[:pos],21)
				self.configurations[directive] = filepath
				continue

			# addtype
			if directive in ['addtype']:
				extension = fields[1]
				if not extension.startswith('.'):
					extension = '.' + extension
				if '/' in extension:
					return (False,'Syntax error in configuration directive: '+line,49)
				self.configurations[directive][extension] = fields[2]
				continue
	
			# directory
			if directive in ['errordocumentroot']:
				if not os.path.isdir(os.path.abspath(fields[1])):
					return (False, 'Folder does not exist: '+line,22)
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
						return (False, 'User does not exist: '+line,23)
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
						return (False, 'Group does not exist: '+line,24)
				continue

			# string directive
			self.configurations[directive] = fields[1]
	
		for directive in self.configurations.keys():
			if self.configurations[directive] == None:
				return (False, 'Mandatory directive not specified: '+directive,25)


		# init main logger
		logging.getLogger('sws').setLevel(logging.INFO)
		self.initLogger('sws',self.configurations['errorlogfile'],self.configurations['accesslogfile'])


		# parse virtualhosts

		# check if sites enabled folder exists
		sitesEnabled = os.path.abspath(self.configFolder + sep + SwsConfiguration.SITES_ENABLED_FOLDER)
		if not os.path.isdir(sitesEnabled):
			return (False, 'Folder does not exists: '+sitesEnabled,26)
	
		# process every .conf file in the sites-enabled folder
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

			curDirectory = '/'
			directoryOpen = False

			for line in lines:

				# process every line of a configuration file
				line = line.strip()

				# check for <directory> directive
				m = re.match(r'<[Dd][Ii][Rr][Ee][Cc][Tt][Oo][Rr][Yy]\s+"(.+)"\s*>',line,re.DOTALL)
				if m != None and self.virtualHosts[vHost]['documentroot'] == None:
					return (False,'Please specifiy Documentroot before: '+line,27)

				if m != None and directoryOpen:
					return (False,'Nesting of <Directory> directives not allowed: '+line,28)

				if m != None:
					directoryOpen = True
					curDirectory = path.abspath(self.virtualHosts[vHost]['documentroot'] + sep + m.group(1))[len(self.virtualHosts[vHost]['documentroot']):]
					if curDirectory == '':
						curDirectory = '/'
					if curDirectory not in self.virtualHosts[vHost]['directory'].keys():
						self.virtualHosts[vHost]['directory'][curDirectory] = self.initDirectory()
					continue

				
				m2 = re.match(r'</[Dd][Ii][Rr][Ee][Cc][Tt][Oo][Rr][Yy]>',line,re.DOTALL)
				if m2 != None and directoryOpen:
					directoryOpen = False
					curDirectory = '/'
					continue

				fields = line.split()
	
				if len(fields) < 1:
					return (False, 'Syntax error in configuration directive: '+line,29)
	
				directive = fields[0].lower()

				if directoryOpen and directive not in ['directoryindex','cgihandler','setoutputfilter','addheader','stopinheritance','addtype']:
					return (False,'Directive not allowed in <Directory>: '+directive,30)

				# defaultvirtualhost
				if directive in ['defaultvirtualhost']:
					if self.defaultVirtualHost == None:
						self.defaultVirtualHost = vHost
						continue
					else:
						return (False,'Multiple Default VirtualHosts',31)

				if directive not in self.virtualHosts[vHost].keys() and directive not in self.virtualHosts[vHost]['directory']['/'].keys():
					return (False, 'Unknown configuration directive: '+line,32)

				if len(fields) < 2:
					return (False, 'Syntax error in configuration directive: '+line,33)

				if directive in ['errordocument','addtype'] and len(fields) != 3:
					return (False, 'Syntax error in configuration directive: '+line,34)

				if directive not in ['errordocument','directoryindex','serveralias','cgihandler','addtype','extfilterdefine','addheader','stopinheritance'] and len(fields) != 2:
					return (False, 'Syntax error in configuration directive: '+line,35)

				if directive in ['cgihandler'] and len(fields) > 3:
					return (False, 'Syntax error in configuration directive: '+line,47)


				if directive in ['addheader']:
					header = fields[1].replace('"','')
					args = ''
					i = 2
					while i < len(fields):
						if i != 2:
							args = args + ' ' + fields[i]
						else:
							args = args + fields[i]
						i = i + 1
					m = re.match(r'"(.+)"',args,re.DOTALL)
					if m == None or header == '':
						return (False, 'Syntax error in configuration directive: '+line,54)
					self.virtualHosts[vHost]['directory'][curDirectory][directive][header] = m.group(1)
					continue

				if directive in ['extfilterdefine']:
					args = ''
					i = 2
					while i < len(fields):
						if i != 2:
							args = args + ' ' + fields[i]
						else:
							args = args + fields[i]
						i = i + 1
					m = re.match(r'cmd\s*=\s*"(.+)"',args,re.DOTALL)
					if m == None:
						return (False, 'Syntax error in configuration directive: '+line,50)
					if fields[1] in self.virtualHosts[vHost][directive].keys():
						return (False, 'Duplicate filter definition: '+line,51)
					self.virtualHosts[vHost][directive][fields[1]] = m.group(1).split()
					continue

				if directive in ['setoutputfilter']:
					if len(self.virtualHosts[vHost]['directory'][curDirectory][directive]) != 0:
						return (False, 'Not allowed to define multiple filter chains in one directory: '+line,52)
					filters = fields[1].split(';')
					for f in filters:
						if f not in self.virtualHosts[vHost]['extfilterdefine'].keys():
							return (False, 'Unknown filter: '+f,53)
						self.virtualHosts[vHost]['directory'][curDirectory][directive].append(f)
					continue

				# multiple values
				if directive in ['serveralias']:
					first = False
					for field in fields:
						if not first:
							first = True
							continue
						self.virtualHosts[vHost][directive].append(field)
					continue

				# possible multiple values
				if directive in ['stopinheritance']:
					first = False
					for field in fields:
						if not first:
							first = True
							continue
						field = field.lower()
						if field not in self.virtualHosts[vHost]['directory'][curDirectory][directive].keys() and field not in ['all']:
							return (False, 'Syntax error in configuration directive: '+line,55)
						if field == 'all':
							for k in self.virtualHosts[vHost]['directory'][curDirectory][directive].keys():
								self.virtualHosts[vHost]['directory'][curDirectory][directive][k] = True
						else:
							self.virtualHosts[vHost]['directory'][curDirectory][directive][field] = True
					continue


				# multiple values in <directory>
				if directive in ['directoryindex']:
					first = False
					for field in fields:
						if not first:
							first = True
							continue
						self.virtualHosts[vHost]['directory'][curDirectory][directive].append(field)
					continue

				# cgihandler
				if directive in ['cgihandler']:
					extension = fields[1]
					if not extension.startswith('.'):
						extension = '.' + extension
					if '/' in extension:
						return (False,'Syntax error in configuration directive: '+line,44)
					executor = None
					if len(fields) == 3:
						executor = os.path.abspath(fields[2])
						if not os.path.isfile(executor):	
							return (False,'CGI Executor could not be found: '+executor,45)
						if not os.access(executor,os.X_OK):	
							return (False,'CGI Executor is not an executable file: '+executor,46)

					self.virtualHosts[vHost]['directory'][curDirectory][directive].append({'extension':extension,'executor':executor})
					continue

				# directory
				if directive in ['documentroot','errordocumentroot']:
					if not os.path.isdir(os.path.abspath(fields[1])):
						return (False, 'Folder does not exist: '+line,36)
					self.virtualHosts[vHost][directive] = os.path.abspath(fields[1])
					continue

				# errordocument
				if directive in ['errordocument']:
					code = -1
					try:
						code = int(fields[1])
					except:
						return (False, 'Type error in code of errordocument directive: '+line,37)
					if not code in self.configurations[directive].keys():
						return (False, 'Error code not supported by server: '+line,38)
					self.virtualHosts[vHost]['errordocument'][code] = fields[2]
					continue

				# addtype
				if directive in ['addtype']:
					extension = fields[1]
					if not extension.startswith('.'):
						extension = '.' + extension
					if '/' in extension:
						return (False,'Syntax error in configuration directive: '+line,48)
					self.virtualHosts[vHost]['directory'][curDirectory][directive][extension] = fields[2]
					continue

				# file
				if directive in ['errorlogfile','accesslogfile']:
					filepath = os.path.abspath(fields[1])
					pos = filepath.rfind(sep)
					if not os.path.isdir(filepath[:pos]):
						return (False, 'Folder does not exist: '+filepath[:pos],39)
					self.virtualHosts[vHost][directive] = filepath
					continue

				# string directive
				self.virtualHosts[vHost][directive] = fields[1]


			if directoryOpen:
				return (False, 'Missing </Directory> directive',40)

		if len(self.virtualHosts) == 0:
			return (False, 'No VirtualHost specified',41)

		if self.defaultVirtualHost == None:
			return (False, 'No DefaultVirtualHost specified',42)


		# check for mandatory directives
		for vHost in self.virtualHosts.keys():	
			# set logger
			self.initLogger(vHost,self.virtualHosts[vHost]['errorlogfile'],self.virtualHosts[vHost]['accesslogfile'])

		# check for mandatory directives
		for vHost in self.virtualHosts.keys():
			for directive in self.virtualHosts[vHost].keys():
				if self.virtualHosts[vHost][directive] == None:
					return (False, 'Mandatory directive ('+directive+') not specified in VirtualHost: '+vHost,43)

		return (True,'Parsing OK',0)

