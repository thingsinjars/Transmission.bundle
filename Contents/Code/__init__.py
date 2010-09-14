from PMS			import Plugin, Log, XML, HTTP, JSON, Prefs, Utils
from PMS.MediaXML	import MediaContainer, MessageContainer, DirectoryItem, VideoItem, SearchDirectoryItem, PopupDirectoryItem
from PMS.FileTypes	import PLS
from PMS.Shorthand	import _L
from lxml			import etree, html
from texttime		import prettyduration
from textbytes		import prettysize
from icon			import torrenticon
import urllib, urllib2, base64, time

TRANSMISSION_PLUGIN_PREFIX		= "/video/transmission"

TRANSMISSION_WAITING			= 1
TRANSMISSION_CHECKING			= 2
TRANSMISSION_DOWNLOADING		= 4
TRANSMISSION_SEEDING			= 8
TRANSMISSION_PAUSED				= 16


def Start():
	Prefs.Expose("hostname", "Hostname")
	Prefs.Expose("username", "Username")
	Prefs.Expose("password", "Password")

	Plugin.AddRequestHandler(TRANSMISSION_PLUGIN_PREFIX, HandleRequest, "Transmission", "icon-default.png", "art-default.jpg")
	Plugin.AddViewGroup("Torrents",	viewMode="InfoList",	contentType="items")
	Plugin.AddViewGroup("Files",	viewMode="InfoList",		contentType="items")
	Plugin.AddViewGroup("Settings",	viewMode="InfoList",		contentType="items")
	Plugin.AddViewGroup("Search",	viewMode="InfoList",		contentType="items")

def getPref(key, default=False):
	value = Prefs.Get(key)
	if value != None:
		return value

	if default == True:
		if key == "hostname":
			return "127.0.0.1:9091"
		if key == "username":
			return ""
		if key == "password":
			return ""

	return None

def getsession():
	url = "http://%s/transmission/rpc/" % (getPref("hostname", True))
	request = {
		"method":		"session-get"
	}
	headers = {}
	# Setup authentication
	u = getPref("username")
	p = getPref("password")
	if u != None and p != None:
		headers["Authorization"] = "Basic %s" % (base64.encodestring("%s:%s" % (u, p))[:-1])
	try:
		body = urllib2.urlopen(urllib2.Request(url, JSON.StringFromDict(request), headers)).read()
	except urllib2.HTTPError, e:
		if e.code == 401 or e.code == 403:
			return "Invalid username or password", {}
		# Otherwise, we've probably received a 409 Conflict which contains the session ID
		return e.hdrs['X-Transmission-Session-Id']
	except:
		return "Transmission not running", {}
	

def remote(method, arguments = {}, headers = {}): 
	url = "http://%s/transmission/rpc/" % (getPref("hostname", True))
	
  #Session ID is now required with every RPC call as of Tranmission 1.53
	session_id = getsession()
	
	request = {
		"method":		method,
		"arguments":	arguments
	}

	# Setup authentication
	u = getPref("username")
	p = getPref("password")
	if u != None and p != None:
		headers["Authorization"] = "Basic %s" % (base64.encodestring("%s:%s" % (u, p))[:-1])
	
	headers["X-Transmission-Session-Id"] = session_id
	
	# Log.Add("Sending Request: %s" % JSON.StringFromDictngFromDict(request))
	try:
		body = urllib2.urlopen(urllib2.Request(url, JSON.StringFromDict(request), headers)).read()
	except urllib2.HTTPError, e:
		if e.code == 401 or e.code == 403:
			return "Invalid username or password", {}

		Log.Add("HTTP error %d from Transmission\n%s" % (e.code, e.read()))
		return "Error reading response from Transmission", {}
	except:
		return "Transmission not running", {}

	# Log.Add("Read Result: %s" % body)
	result = JSON.DictFromString(body)

	if result["result"] == "success":
		result["result"] = None

	if result["arguments"] == None:
		result["arguments"] = {}

	return result["result"], result["arguments"]

def torrentstatus(torrent):
	if torrent == None or torrent["status"] == None:
		return "Unknown"
	elif torrent["status"] == TRANSMISSION_WAITING:
		return "Waiting to verify"
	elif torrent["status"] == TRANSMISSION_CHECKING:
		return "Verifying local data"
	elif torrent["status"] == TRANSMISSION_PAUSED:
		return "Paused"
	elif torrent["status"] == TRANSMISSION_DOWNLOADING:
		return "Downloading"
	elif torrent["status"] == TRANSMISSION_SEEDING:
		return "Seeding"
	else:
		return "Unknown"
 
def HandleRequest(path, count):
	Log.Add("Transmission got request: %s" % ("/".join(path)))

	if count == 0:
		# Display a list of torrents, with a detailed summary
		# ###################################################
		dir				= MediaContainer('art-default.jpg', "Torrents", "Torrents")
		progress		= -1;
		error, result	= remote("torrent-get",
			{ "fields": [
				"hashString",			"name",				"status",
				"eta",					"errorString",

				"totalSize",			"leftUntilDone",	"sizeWhenDone",
				"peersGettingFromUs",	"peersSendingToUs",	"peersConnected",

				"rateDownload",			"rateUpload",
				"downloadedEver",		"uploadedEver"
			] }
		)

		if error != None:
			dir.AppendItem(DirectoryItem("setup",	"Installation and Setup",
				summary="Transmission is not running.\n\nPlease ensure you have downloaded the application from transmissionbt.com and enabled remote access.\n\n",
				thumb=Plugin.ExposedResourcePath("icon-default.png")))
      # dir.SetMessage("Torrents", error)
		elif result["torrents"] != None:
			for torrent in result["torrents"]:
				summary = ""

				if torrent["errorString"]:
					summary += "Error: %s\n" % (torrent["errorString"])

				if torrent["leftUntilDone"] > 0 and torrent["status"] != TRANSMISSION_SEEDING:
					# Display progress "12.3 MB of 45.6 GB (0%)"
					progress = ((torrent["sizeWhenDone"] - torrent["leftUntilDone"]) /
								(torrent["sizeWhenDone"] / 100))

					summary += "%s of %s (%d%%)\n" % (
							prettysize(torrent["sizeWhenDone"] - torrent["leftUntilDone"]),
							prettysize(torrent["sizeWhenDone"]), progress
						)

					# Display an ETA; "3 days remaining"
					if torrent["eta"] > 0 and torrent["status"] != TRANSMISSION_PAUSED:
						summary += prettyduration(torrent["eta"]) + " remaining\n"
					else:
						summary += "Remaining time unknown\n"

					if torrent["status"] == TRANSMISSION_DOWNLOADING:
						# Display download status "Downloading from 3 of 6 peers"
						summary += "Downloading from %d of %d peers\n" % (
								torrent["peersSendingToUs"],
								torrent["peersConnected"]
							)

						# Display download and upload rates
						summary += "Downloading at %s/s\nUploading at %s/s\n" % (
								prettysize(torrent["rateDownload"]),
								prettysize(torrent["rateUpload"])
							)
					else:
						# Display torrent status
						summary += torrentstatus(torrent)
				else:
					if torrent["status"] == TRANSMISSION_SEEDING:
						summary += "Complete\n"
						progress=100
					else:
						Log.Add("torrent status is: %d" % torrent["status"])

					if torrent["downloadedEver"] == 0:
						torrent["downloadedEver"] = 1

					summary += "%s, uploaded %s (Ratio %.2f)\n" % (
							prettysize(torrent["totalSize"]), 
							prettysize(torrent["uploadedEver"]), 
							float(torrent["uploadedEver"]) / float(torrent["downloadedEver"])
						)

					if torrent["status"] == TRANSMISSION_SEEDING:
						summary += "Seeding to %d of %d peers\n" % (
								torrent["peersGettingFromUs"],
								torrent["peersConnected"]
							)
						summary += "Uploading at %s/s\n" % (
								prettysize(torrent["rateUpload"])
							)


				# The summary has been built, add the item
				dir.AppendItem(PopupDirectoryItem("%s/%d/%d" % (
						torrent["hashString"], torrent["status"],
						time.time() / 120
					),
					torrent["name"], summary=summary,
					thumb="%s/icons/%s/%s/%d" % (
						TRANSMISSION_PLUGIN_PREFIX,
						urllib.quote(torrent["name"]),
						urllib.quote("%d%%" % progress),
						progress
					)))

			
			dir.AppendItem(DirectoryItem("all/0/0/torrent-stop",	"Pause All",
				summary="Pause all torrents that are currently downloading",
				thumb=Plugin.ExposedResourcePath("pause-hi.png")))
			dir.AppendItem(DirectoryItem("all/0/0/torrent-start",	"Resume All",
				summary="Resume all paused torrents",
				thumb=Plugin.ExposedResourcePath("resume-hi.png")))

		dir.AppendItem(DirectoryItem("search", "Search for new Torrents",
			summary="Search for new torrents",
			thumb=Plugin.ExposedResourcePath("search-hi.png")))
		dir.AppendItem(DirectoryItem("settings", "Settings",
			summary="Modify your settings",
			thumb=Plugin.ExposedResourcePath("settings-hi.png")))
		return dir.ToXML()

	elif path[0] == "search":
		if count == 1:
			# Display a list of search sites
			# ##############################
			# /search
			dir = MediaContainer('art-default.jpg', "Search", "Search")
			dir.AppendItem(DirectoryItem("mininova", "Mininova"))
			dir.AppendItem(DirectoryItem("isohunt", "isoHunt"))
			dir.AppendItem(SearchDirectoryItem("ezrss/99", "EZRSS (tvrss.net)", "ezrss"))

			return dir.ToXML()

		if path[1] == "mininova":
			if count == 2:
				# Display a list of categories
				# ############################
				dir = MediaContainer('art-default.jpg', "Search", "Search")
				dir.AppendItem(SearchDirectoryItem("0", "Search all categories", "Search"))

				dir.AppendItem(DirectoryItem("4", "Movies"))
				dir.AppendItem(DirectoryItem("8", "TV shows"))
				dir.AppendItem(DirectoryItem("6", "Pictures"))
				dir.AppendItem(DirectoryItem("5", "Music"))
				dir.AppendItem(DirectoryItem("1", "Anime"))
				dir.AppendItem(DirectoryItem("2", "Books"))
				dir.AppendItem(DirectoryItem("3", "Games"))
				dir.AppendItem(DirectoryItem("7", "Software"))
				dir.AppendItem(DirectoryItem("9", "Other"))

				return dir.ToXML()
			elif count == 3 or count == 4:
				# Search mininova and display a list of results
				# #############################################
				# /search/mininova/2/Search%20String
				category	= int(path[2])
				if count == 4:
					query	= urllib.quote_plus(path[3])
				else:
					query	= None

				url = "http://mininova.org/rss"
				if query != None:
					url += "/%s" % query
				if category != 0:
					# 0 == all
					url += "/%d" % category

				Log.Add("Searching mininova with URL: %s" % url)

				dir = MediaContainer('art-default.jpg', "Search", "Search")
				if query == None:
					# Add a search item
					dir.AppendItem(SearchDirectoryItem("%s/search/mininova/%d" % (TRANSMISSION_PLUGIN_PREFIX, category),
						"Search", "Search"))

				# Send the request
				rss = XML.ElementFromURL(url)

				#if there's no response at all
				if rss == None:
					return MessageContainer("Error", "Search failed").ToXML()

				#If there are no results
				if rss.find("channel/item") == None:
					return MessageContainer("Error", "No results").ToXML()

				# Parse the results document
				for item in rss.find("channel").iter("item"):
					summary  = "%s\n" % item.find("title").text
					summary += "Category: %s\n" % item.find("category").text
					summary += "Size: %s\n" % prettysize(int(item.find("enclosure").get("length")))

					# If there was no query for this item then add a - instead
					if query == None:
						p = "-/"
					else:
						p = ""

					# Find the ID so it can be passed through.  The enclosure URL will be
					# rebuilt with it later.
					p += item.find("enclosure").get("url").rsplit("/", 1)[1]

					Log.Add(p)
					dir.AppendItem(PopupDirectoryItem(
						p, (item.find("title").text),
						"", summary=summary))

				return dir.ToXML()
			elif count == 5:
				# Display options for a torrent
				# #############################
				# /search/mininova/2/Search%20String/url

				dir = MediaContainer('art-default.jpg', "Actions", "Actions")
				dir.AppendItem(DirectoryItem("download", "Download"))
				return dir.ToXML()

			elif count == 6:
				# Perform an action on a torrent
				# ##############################
				# /search/mininova/2/Search%20String/url/action
				itemid	= int(path[4])
				action	= path[5]

				if action == "download":
					error, result = remote("torrent-add", { "filename": "http://www.mininova.org/get/%d" % itemid })
					if error == None:
						return MessageContainer("Search", "Added Torrent").ToXML()
					else:
						return MessageContainer("Search", error).ToXML()
				else:
					return MessageContainer("Search", "Unknown action").ToXML()

		elif path[1] == "isohunt":
			if count == 2:
				# Display a list of categories
				# ############################
				dir = MediaContainer('art-default.jpg', "Search", "Search")
				dir.AppendItem(SearchDirectoryItem("99", "Search all categories", "Search"))

				dir.AppendItem(DirectoryItem("1", "Movies"))
				dir.AppendItem(DirectoryItem("2", "Audio"))
				dir.AppendItem(DirectoryItem("3", "TV shows"))
				dir.AppendItem(DirectoryItem("4", "Games"))
				dir.AppendItem(DirectoryItem("10", "Music Video"))
				dir.AppendItem(DirectoryItem("5", "Applications"))
				dir.AppendItem(DirectoryItem("7", "Pictures"))
				dir.AppendItem(DirectoryItem("8", "Comics"))
				dir.AppendItem(DirectoryItem("9", "Books"))
				dir.AppendItem(DirectoryItem("0", "Miscellaneous"))
				dir.AppendItem(DirectoryItem("11", "Unclassified"))

				return dir.ToXML()
			elif count == 3 or count == 4:
				# Search isohunt and display a list of results
				# #############################################
				# /search/isohunt/2/Search%20String
				category	= int(path[2])
				if count == 4:
					query	= urllib.quote_plus(path[3])
				else:
					query	= None

				url = "http://isohunt.com/js/rss"
				if query != None:
					url += "/%s" % query
				if category != 99:
					# 99 == all
					url += "?iht=%d" % category

				Log.Add("Searching isohunt with URL: %s" % url)

				dir = MediaContainer('art-default.jpg', "Search", "Search")
				if query == None:
					# Add a search item
					dir.AppendItem(SearchDirectoryItem("%s/search/isohunt/%d" % (TRANSMISSION_PLUGIN_PREFIX, category),
						"Search", "Search"))

				# Send the request
				rss = XML.ElementFromURL(url)

				#if there's no response at all
				if rss == None:
					return MessageContainer("Error", "Search failed").ToXML()

				#If there are no results
				if rss.find("channel/item") == None:
					return MessageContainer("Error", "No results").ToXML()

				# Parse the results document
				for item in rss.find("channel").iter("item"):
					summary  = "%s\n" % item.find("title").text
					summary += "Category: %s\n" % item.find("category").text
					summary += "Size: %s\n" % prettysize(int(item.find("enclosure").get("length")))

					# If there was no query for this item then add a - instead
					if query == None:
						p = "-/"
					else:
						p = ""

					# Find the ID so it can be passed through.  The enclosure URL will be
					# rebuilt with it later.
					p += item.find("enclosure").get("url").rsplit("/", 2)[1]

					Log.Add(p)
					dir.AppendItem(PopupDirectoryItem(
						p, (item.find("title").text),
						"", summary=summary))

				return dir.ToXML()
			elif count == 5:
				# Display options for a torrent
				# #############################
				# /search/isohunt/2/Search%20String/url

				dir = MediaContainer('art-default.jpg', "Actions", "Actions")
				dir.AppendItem(DirectoryItem("download", "Download"))
				return dir.ToXML()

			elif count == 6:
				# Perform an action on a torrent
				# ##############################
				# /search/isohunt/2/Search%20String/url/action
				itemid	= int(path[4])
				action	= path[5]

				if action == "download":
					error, result = remote("torrent-add", { "filename": "http://www.isohunt.com/download/%d" % itemid })
					if error == None:
						return MessageContainer("Search", "Added Torrent").ToXML()
					else:
						return MessageContainer("Search", error).ToXML()
				else:
					return MessageContainer("Search", "Unknown action").ToXML()

		elif path[1] == "ezrss":
			if count == 2:
				# Display a list of categories
				# ############################
				dir = MediaContainer('art-default.jpg', "Search", "Search")
				dir.AppendItem(SearchDirectoryItem("99", "Search EZRSS", "Search"))

				return dir.ToXML()
			elif count == 3 or count == 4:
				# Search ezrss and display a list of results
				# #############################################
				# /search/ezrss/99/Search%20String
				category	= int(path[2])
				if count == 4:
					query	= urllib.quote_plus(path[3])
				else:
					query	= None

				url = "http://ezrss.it/search/index.php?simple&mode=rss&show_name="
				if query != None:
					url += "%s" % query

				Log.Add("Searching ezrss with URL: %s" % url)

				dir = MediaContainer('art-default.jpg', "Search", "Search")
				if query == None:
					# Add a search item
					dir.AppendItem(SearchDirectoryItem("%s/search/isohunt/%d" % (TRANSMISSION_PLUGIN_PREFIX, category),
						"Search", "Search"))

				# Send the request
				rss = XML.ElementFromURL(url)

				#if there's no response at all
				if rss == None:
					return MessageContainer("Error", "Search failed").ToXML()

				#If there are no results
				if rss.find("channel/item") == None:
					return MessageContainer("Error", "No results").ToXML()

				# Parse the results document
				for item in rss.find("channel").iter("item"):
					summary  = "%s\n" % item.find("title").text
					summary += "Category: %s\n" % item.find("category").text
					summary += "Size: %s\n" % prettysize(int(item.find("enclosure").get("length")))

					# If there was no query for this item then add a - instead
					if query == None:
						p = "-/"
					else:
						p = ""

					# Find the ID so it can be passed through.  The enclosure URL will be
					# rebuilt with it later.
					# http://torrent.zoink.it/House.S06E12.720p.HDTV.x264-IMMERSE.[eztv].torrent
					p += Utils.EncodeStringToUrlPath(item.find("enclosure").get("url").rsplit("/", 1)[1])

					Log.Add(p)
					dir.AppendItem(PopupDirectoryItem(p, (item.find("title").text), "", summary=summary))

				return dir.ToXML()
			elif count == 5:
				# Display options for a torrent
				# #############################
				# /search/isohunt/2/Search%20String/url

				dir = MediaContainer('art-default.jpg', "Actions", "Actions")
				dir.AppendItem(DirectoryItem("download", "Download"))
				return dir.ToXML()

			elif count == 6:
				# Perform an action on a torrent
				# ##############################
				# /search/isohunt/2/Search%20String/url/action
				itemid	= path[4]
				action	= path[5]

				if action == "download":
					error, result = remote("torrent-add", { "filename": "http://torrent.zoink.it/%s" % Utils.DecodeUrlPathToString(itemid) })
					if error == None:
						return MessageContainer("Search", "Added Torrent").ToXML()
					else:
						return MessageContainer("Search", error).ToXML()
				else:
					return MessageContainer("Search", "Unknown action").ToXML()
	elif path[0] == "settings":
		if count == 1:
			# Display a list of user settings
			# ###############################
			# /settings

			dir = MediaContainer('art-default.jpg', "Settings", "Settings")
			dir.nocache = 1
			dir.AppendItem(SearchDirectoryItem("plex/hostname",
				"Host or IP: %s" % getPref("hostname", True), "Hostname",
				summary="Enter the hostname and port of the computer running Transmission.  The remote access option must be enabled."))  
			dir.AppendItem(SearchDirectoryItem("plex/username",
				"Username: %s" % getPref("username", True), "Username",
				summary="Set the username to match the remote access username in your Transmission preferences."))
			dir.AppendItem(SearchDirectoryItem("plex/password",
				"Password", "Password",
				summary="Set the password to match the remote access password in your Transmission preferences."))

			# Disable the plex session settings until I can get them working better
			if False:
				error, result = remote("session-get")
				try:
					if result["arguments"]["speed-limit-down-enabled"] == 1:
						dir.AppendItem(SearchDirectoryItem("transmission/speed-limit-down",
							"Download limit: %d" % result["arguments"]["speed-limit-down"], "Max Download Rate"))
						dir.AppendItem(DirectoryItem("transmission/speed-limit-down-enabled/0", "Disable download limit"))
					else:
						dir.AppendItem(DirectoryItem("transmission/speed-limit-down-enabled/1", "Enable download limit"))

					if result["arguments"]["speed-limit-up-enabled"] == 1:
						dir.AppendItem(SearchDirectoryItem("transmission/speed-limit-up",
							"Upload limit: %d" % result["arguments"]["speed-limit-up"], "Max Upload Rate"))
						dir.AppendItem(DirectoryItem("transmission/speed-limit-up-enabled/0", "Disable upload limit"))
					else:
						dir.AppendItem(DirectoryItem("transmission/speed-limit-up-enabled/1", "Enable upload limit"))
				except KeyError:
					if error:
						Log.Add("Error from Transmission while trying to get settings: %s" % error)

			return dir.ToXML()
		elif path[1] == "plex":
			# Store a user setting
			# ####################
			# /settings/plex/name/value

			Prefs.Set(path[2], path[3])
			
			#This avoids 'Request not handled' error
			#return MessageContainer("Saved", "Setting has been saved").ToXML()
		elif path[1] == "transmission":
			# Store a transmission setting
			# ############################
			# /settings/transmission/name/value

			error, result = remote("session-set", { path[2]: path[3] } )
			if error != None:
				return MessageContainer("Error", error).ToXML()

	elif path[0] == "icons":
		if count >= 4:
			# Return an icon that includes the torrent's name and progress to
			# allow a quicker nicer way to see your torrents.
			# ###############################################################
			# /icons/name/status/progress/time

			return torrenticon(urllib.unquote(path[1]), urllib.unquote(path[2]), int(path[3]))

	elif path[0] == "setup":
		return MessageContainer("Error", "Please ensure Transmission is installed and running.").ToXML()
	elif count == 1:
		return MessageContainer("Error", "Invalid Request").ToXML()

	elif count == 2 or count == 3:
		# Display an action menu for this torrent
		# #######################################
		# /id/status
		# /id/status/time
		id		= path[0]
		status	= int(path[1])

		dir = MediaContainer('art-default.jpg', "Actions", "Actions")

		dir.AppendItem(DirectoryItem("files",	"View Files"))
		if status == TRANSMISSION_PAUSED:
			dir.AppendItem(DirectoryItem("torrent-start",	"Resume"))
		else:
			dir.AppendItem(DirectoryItem("torrent-stop",	"Pause"))
		dir.AppendItem(DirectoryItem("torrent-remove",		"Remove From List"))
		dir.AppendItem(DirectoryItem("torrent-delete",		"Remove Data"))

		return dir.ToXML()

	elif path[3] == "files":
		if count == 4:
			# Display the contents of a torrent
			# #################################
			# /id/status/files
			id		= path[0]
			status	= int(path[1])

			Log.Add("Need details for: %s" % id)

			error, result = remote("torrent-get",
				{ "ids": [ id ], "fields": [ "hashString", "files", "wanted" ] })

			if error != None:
				return MessageContainer("Files", error).ToXML()

			dir = MediaContainer('art-default.jpg', "Files", "Files")
			for torrent in result["torrents"]:
				if torrent["hashString"] != id:
					continue

				for i in range(0, len(torrent["files"])):
					file = torrent["files"][i]

					Log.Add("Name: %s" % (file["name"]))

					if torrent["wanted"][i] == 1:
						if file["bytesCompleted"] == file["length"]:
							summary = "Complete"
						else:
							# Display progress "12.3 MB of 45.6 GB (0%)"
							summary = "%s of %s (%s%%)\n" % (
									prettysize(file["bytesCompleted"]),
									prettysize(file["length"]),
									(file["bytesCompleted"]) / (file["length"] / 100)
								)
					else:
						summary = "Not Downloading"

					dir.AppendItem(PopupDirectoryItem("%d" % i, file["name"], summary=summary))

			return dir.ToXML()

		elif count == 5:
			# Display an action menu for this file
			# ####################################
			# /id/status/files/filename
			id		= path[0]
			status	= int(path[1])
			fileid	= int(path[4])

			# dir.AppendItem(DirectoryItem("play",	"Play File"))
			error, result = remote("torrent-get",	{ "ids": [ id ], "fields": [ "hashString", "files", "downloadDir" ] })

			if error != None:
				return MessageContainer("Files", error).ToXML()

			dir = MediaContainer(art='art-default.jpg', title1="Actions", viewGroup="Actions")

			for torrent in result["torrents"]:
				if torrent["hashString"] != id:
					continue
					
				for i in range(0, len(torrent["files"])):
					file = torrent["files"][i]
					filePath = torrent['downloadDir']+'/'+file["name"]
					
					#commented out as you can't play a local file from a plugin
					# dir.AppendItem(VideoItem(VideoURLFromLocation(filePath), "Play File", "", "", None))
			
			return dir.ToXML()

		elif count == 6:
			
			# Perform an action on a specific file
			# ####################################
			# /id/status/files/filename/action
			id		= path[0]
			status	= int(path[1])
			fileid	= int(path[4])
			action	= path[5]

			Log.Add("Implement file action: %s" % path[5])

	else:
		# Perform an action
		# #################
		# /id/status/time/action
		id		= path[0]
		status	= int(path[1])
		action	= path[3]
		

		arguments = { }
		if id != "all":
			arguments["ids"] = [ id ]

		if action == "torrent-delete":
			# Special case.  Do a torrent-remove, but turn on the
			# "delete-local-data" option
			action = "torrent-remove"
			arguments["delete-local-data"] = True

		error, result = remote(action, arguments)
		if error != None:
			return MessageContainer("Error", error)

		return MessageContainer("Transmission", "Action completed").ToXML()
		

def ContainerFromJSONName(jsonName):
	dir = MediaContainer('art-default.jpg', title1="Transmission", title2=_L(jsonName))

	return dir.ToXML()

def VideoURLFromLocation(location):
	#If there is ever a system to allow plugins to play local files, that would go here.
	return None

def VideoPlaylist(path, count):
	#Similarly, this would play a directoy of files
	return None

