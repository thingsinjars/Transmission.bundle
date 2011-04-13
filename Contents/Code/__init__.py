from texttime import prettyduration
from textbytes import prettysize
import urllib, urllib2, base64 #temporarily included until HTTP module allows header access

####################################################################################################

PLUGIN_PREFIX = "/video/transmission"
PLUGIN_TITLE = "Transmission"

NAME = L('Title')

ART           = 'art-default.jpg'
ICON          = 'icon-default.png'
SETTINGS      = 'settings-hi.png'
PAUSE         = 'pause-hi.png'
RESUME        = 'resume-hi.png'
SEARCH        = 'search-hi.png'
TV            = 'tv-hi.png'

# Plugin-specific constants
TRANSMISSION_WAITING      = 1
TRANSMISSION_CHECKING     = 2
TRANSMISSION_DOWNLOADING  = 4
TRANSMISSION_SEEDING      = 8
TRANSMISSION_PAUSED       = 16

####################################################################################################

def Start():
    Plugin.AddPrefixHandler(PLUGIN_PREFIX, MainMenu, PLUGIN_TITLE, ICON, ART)
    Plugin.AddViewGroup('List', viewMode='List', mediaType='items')

    MediaContainer.art = R(ART)
    MediaContainer.title1 = NAME
    DirectoryItem.thumb = R(ICON)

#def CreatePrefs():
#    Prefs.Add(id='hostname', type='text', default='127.0.0.1:9091', label='Hostname')
#    Prefs.Add(id='username', type='text', default='', label='Username (enter a . for empty username)')
#    Prefs.Add(id='password', type='text', default='', label='Password (enter a . for empty password)', option='hidden')

def ValidatePrefs():
    u = Prefs['username']
    p = Prefs['password']
    h = Prefs['hostname']

    ## do some checks and return a
    ## message container
    if( h ):
        return MessageContainer(
            "Success",
            "Details have been saved"
        )
    else:
        return MessageContainer(
            "Error",
            "You need to provide a hostname"
        )

### Transmission plugin proper starts here
# Transmission requires username, password and Session ID to perform actions
# We attempt to make a connection with just username & password so we get the 409 Conflict response
# This will contain a header with our Session ID
def GetSession():
  h = Prefs['hostname']
  u = Prefs['username']
  p = Prefs['password']
  url = "http://%s/transmission/rpc/" % h
  request = { "method" : "session-get" }
  headers = {}
  if( u and p ):
    headers["Authorization"] = "Basic %s" % (base64.encodestring("%s:%s" % (u, p))[:-1])

  try:
    body = urllib2.urlopen(urllib2.Request(url, JSON.StringFromObject(request), headers)).read()
  except urllib2.HTTPError, e:
    if e.code == 401 or e.code == 403:
      return L('ErrorInvalidUsername'), {}
    # Otherwise, we've probably received a 409 Conflict which contains the session ID
    # Once the HTTP module allows access to returned headers, use these to set global authorization:
    # HTTP.SetPassword(h,u,p)
    # HTTP.SetHeader('X-Transmission-Session-Id', e.hdrs['X-Transmission-Session-Id'])
    return e.hdrs['X-Transmission-Session-Id']
  except:
    return L('ErrorNotRunning'), {}

# Remote Transmission Call -
# Use the RPC methods of Transmission to perform all out actions
def RTC(method, arguments = {}, headers = {}):
  # Once the HTTP module allows access to returned headers and the HTTP.SetPassword also auths JSON, refactor this
  h = Prefs['hostname']
  u = Prefs['username']
  p = Prefs['password']
  url = "http://%s/transmission/rpc/" % h

  session_id = GetSession()

  request = {
    "method":    method,
    "arguments":  arguments
  }

  # Setup authentication
  if( u and p ):
    headers["Authorization"] = "Basic %s" % (base64.encodestring("%s:%s" % (u, p))[:-1])

  headers["X-Transmission-Session-Id"] = session_id

  try:
    body = urllib2.urlopen(urllib2.Request(url, JSON.StringFromObject(request), headers)).read()
  except urllib2.HTTPError, e:
    if e.code == 401 or e.code == 403:
      return L('ErrorInvalidUsername'), {}
    return "Error reading response from Transmission", {}
  except urllib2.URLError, e:
    return e.reason, {}

  result = JSON.ObjectFromString(body)

  if result["result"] == "success":
    result["result"] = None

  if result["arguments"] == None:
    result["arguments"] = {}

  return result["result"], result["arguments"]

def MainMenu():
    dir = MediaContainer(viewGroup="List")
    GetSession()
    dir.Append(Function(DirectoryItem(TorrentList,"Torrents",subtitle=None,summary="View torrent progress and control your downloads.",thumb=R(ICON),art=R(ART))))
    dir.Append(Function(DirectoryItem(SearchTorrents,"Search for a torrent",subtitle=None,summary="Browse the TV shows directory or search for files to download.",thumb=R(SEARCH),art=R(ART))))
    dir.Append(PrefsItem(title="Preferences",subtitle="Set Transmission access details",summary="Make sure Transmission is running and 'Remote access' is enabled then enter the access details here.",thumb=R(SETTINGS)))
    return dir

def TorrentList(sender):
  error, result  = RTC("torrent-get",
    { "fields": [
      "hashString","name","status",
      "eta","errorString",
      "totalSize","leftUntilDone","sizeWhenDone",
      "peersGettingFromUs",  "peersSendingToUs",  "peersConnected",
      "rateDownload",      "rateUpload",
      "downloadedEver",    "uploadedEver"
    ] }
  )
  if error != None:
    if error != "Connection refused":
      return MessageContainer(
          "Transmission unavailable",
          "There was an unknown error."
      )
    else:
      return MessageContainer(
          "Transmission unavailable",
          "Please make sure Transmission is running with Remote access enabled.  For more information please see http://wiki.plexapp.com/index.php/Transmission"
      )
  elif result["torrents"] != None:
    dir = MediaContainer()
    progress    = 100;
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
          summary += TorrentStatus(torrent)
      else:
        if torrent["status"] == TRANSMISSION_SEEDING:
          summary += "Complete\n"
          progress=100
        # else:
        #   Log("torrent status is: %d" % torrent["status"], True)

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
      # This is so that we don't bloat the plugin with 101 images.
      # It might change later if PIL is included into the framework
      nearest = int(round(progress/10)*10)

      # The summary has been built, add the item:
      dir.Append(
          Function(
              PopupDirectoryItem(
                  TorrentInfo,
                  torrent["name"],
                  summary=summary,
                  thumb=R("%s.png" % nearest)
              ),
              name = torrent["name"],
              status = torrent["status"],
              hash = torrent["hashString"]
              )
          )

    # Add "Pause all torrents" menu item
    dir.Append(Function(DirectoryItem(PauseTorrent,L('MenuPauseAll'),subtitle=None,summary=None,thumb=R(PAUSE),art=R(ART)), hash='all'))

    # Add "Resume all torrents" menu item
    dir.Append(Function(DirectoryItem(ResumeTorrent,L('MenuResumeAll'),subtitle=None,summary=None,thumb=R(RESUME),art=R(ART)), hash='all'))

    return dir

def TorrentInfo(sender, name, status, hash):
  # Display an action menu for this torrent
  # #######################################
  dir = MediaContainer()
  dir.Append(Function(DirectoryItem(ViewFiles,			L('MenuViewFiles'),	subtitle=None,summary=None,thumb=R(ICON),art=R(ART)), hash=hash))
  if status == TRANSMISSION_PAUSED:
    dir.Append(Function(DirectoryItem(ResumeTorrent,L('MenuResume'),		subtitle=None,summary=None,thumb=R(ICON),art=R(ART)), hash=hash))
  else:
    dir.Append(Function(DirectoryItem(PauseTorrent,	L('MenuPause'),			subtitle=None,summary=None,thumb=R(ICON),art=R(ART)), hash=hash))
  dir.Append(Function(DirectoryItem(RemoveTorrent,	L('MenuRemove'),		subtitle=None,summary=None,thumb=R(ICON),art=R(ART)), hash=hash))
  dir.Append(Function(DirectoryItem(DeleteTorrent,	L('MenuDelete'),		subtitle=None,summary=None,thumb=R(ICON),art=R(ART)), hash=hash))

  return dir

def TorrentStatus(torrent):
  if torrent == None or torrent["status"] == None:
    return L('TorrentStatusUnknown')
  elif torrent["status"] == TRANSMISSION_WAITING:
    return L('TorrentStatusWaiting')
  elif torrent["status"] == TRANSMISSION_CHECKING:
    return L('TorrentStatusVerifying')
  elif torrent["status"] == TRANSMISSION_PAUSED:
    return L('TorrentStatusPaused')
  elif torrent["status"] == TRANSMISSION_DOWNLOADING:
    return L('TorrentStatusDownloading')
  elif torrent["status"] == TRANSMISSION_SEEDING:
    return L('TorrentStatusSeeding')
  else:
    return L('TorrentStatusUnknown')

def ViewFiles(sender, hash):
  # Display the contents of a torrent
  # #################################
  # Log("Need details for: %s" % hash, True)

  error, result = RTC("torrent-get",
      { "ids": [ hash ], "fields": [ "hashString", "files", "wanted" ] })

  if error != None:
    return MessageContainer(
      "Transmission error",
      "Unable to list files."
    )

  dir = MediaContainer()
  for torrent in result["torrents"]:
    if torrent["hashString"] != hash:
      continue

    for i in range(0, len(torrent["files"])):
      f = torrent["files"][i]

      Log("Name: %s" % (f["name"]), True)

      if torrent["wanted"][i] == 1:
        if f["bytesCompleted"] == f["length"]:
          summary = "Complete"
        else:
          # Display progress "12.3 MB of 45.6 GB (0%)"
          summary = "%s of %s (%s%%)\n" % (
              prettysize(f["bytesCompleted"]),
              prettysize(f["length"]),
              (f["bytesCompleted"]) / (f["length"] / 100)
          )
      else:
        summary = "Not Downloading"

      dir.Append(PopupDirectoryItem("%d" % i, f["name"], summary=summary))

    return dir


def ResumeTorrent(sender, hash):
  # The following several functions could have
  # been bundled together but I decided to keep them separate
  # #######################################
  action = "torrent-start"
  arguments = { "ids" : hash }
  error, result = RTC(action, arguments)
  if error != None:
    return MessageContainer("Error", error)
  else:
    return MessageContainer("Transmission", L('ActionTorrentResumed'))

def PauseTorrent(sender, hash):
  action = "torrent-stop"
  arguments = { "ids" : hash }
  error, result = RTC(action, arguments)
  if error != None:
    return MessageContainer("Error", error)
  else:
    return MessageContainer("Transmission", L('ActionTorrentPaused'))

def RemoveTorrent(sender, hash):
  action = "torrent-remove"
  arguments = { "ids" : hash }
  error, result = RTC(action, arguments)
  if error != None:
    return MessageContainer("Error", error)
  else:
    return MessageContainer("Transmission", L('ActionTorrentRemoved'))

def DeleteTorrent(sender, hash):
  action = "torrent-remove"
  arguments = { "ids" : hash, "delete-local-data": True}
  error, result = RTC(action, arguments)
  if error != None:
    return MessageContainer("Error", error)
  else:
    return MessageContainer("Transmission", L('ActionTorrentDeleted'))

def AddTorrent(sender, torrentUrl):
  action = "torrent-add"
  arguments = { "filename" : torrentUrl}
  Log(torrentUrl, True)
  error, result = RTC(action, arguments)
  if error != None:
    return MessageContainer("Error", error)
  else:
    return MessageContainer("Transmission", L('ActionTorrentAdded'))

# These next few extremely handy functions are based on work done in the uTorrent Plugin.
# The first one would list all shows mentioned on http://ezrss.it/shows/
# This is a long list so it isn't used
def TVShowList(sender):

    dir = MediaContainer()

    showsPage = HTML.ElementFromURL('http://ezrss.it/shows/', errors='ignore')

    #Assign to blocks, and remove the first block (A, B, C, etc...)
    blocks = showsPage.xpath('//div[@class="block"]')
    blocks.pop(0)

    for block in blocks:
        for href in block.xpath('.//a'):
            if href.text != "# Top":
                requestUrl = "http://ezrss.it" + href.get("href") + "&mode=rss"
                dir.Append(Function(DirectoryItem(TVEpisodeList,href.text,subtitle=None,summary=None,thumb=R(ICON),art=R(ART)),name=href.text,url=requestUrl))

    return dir

# This grabs a list of all first letters used on that page
def TVShowListFolders(sender):

    dir = MediaContainer()

    showsPage = HTML.ElementFromURL('http://ezrss.it/shows/', errors='ignore')

    #Assign to blocks, and remove the first block (A, B, C, etc...)
    blocks = showsPage.xpath('//div[@class="block"]')
    blocks.pop(0)

    for block in blocks:
        letter = block.xpath("h2")[0].text
        dir.Append(Function(DirectoryItem(TVShowListSubfolders,letter,subtitle=None,summary=None,thumb=R(ICON),art=R(ART)),letter=letter))
    return dir

# This returns only shows within that subsection
def TVShowListSubfolders(sender, letter):

    dir = MediaContainer()

    showsPage = HTML.ElementFromURL('http://ezrss.it/shows/', errors='ignore')

    #Assign to blocks, and remove the first block (A, B, C, etc...)
    blocks = showsPage.xpath('//div[@class="block" and h2 = "%s"]' % letter)

    for block in blocks:
        for href in block.xpath('.//a'):
            if href.text != "# Top":
                requestUrl = "http://ezrss.it" + href.get("href") + "&mode=rss"
                dir.Append(Function(DirectoryItem(TVEpisodeList,href.text,subtitle=None,summary=None,thumb=R(ICON),art=R(ART)),name=href.text,url=requestUrl))

    return dir

# This lists all available torrents for the chosen show
def TVEpisodeList(sender, name, url):

    dir = MediaContainer()

    feed = RSS.FeedFromURL(url)['entries']

    for element in feed:
        title = element["title"]
        link = element["link"]
        dir.Append(Function(DirectoryItem(AddTorrent, title=title,thumb=R(ICON), art=R(ART)), torrentUrl=link))

    return dir

# There's a minor bug in the InputDirectoryItem in that it doesn't
# like it when subtitle is passed as a named argument. Just saying.
def SearchTorrents(sender):
  dir = MediaContainer(viewGroup="List")
  dir.Append(Function(DirectoryItem(			TVShowListFolders,		L('MenuBrowseTV'),		subtitle="Browse the TV shows directory",	summary=None,thumb=R(TV),art=R(ART))))
  dir.Append(Function(InputDirectoryItem(	SearchEZTV,						L('MenuSearchTV'),		"Search the TV shows directory",	summary="This will use EZTV to search.",thumb=R(SEARCH),art=R(ART))))
  dir.Append(Function(DirectoryItem(			SearchIsoHunt,				L('MenuSearchOther'),	subtitle="Search for other torrents",			summary="This will use IsoHunt to search.",thumb=R(SEARCH),art=R(ART))))
  return dir

# I might drop IsoHunt from the next version as it returns a lot of...ahem...adult results regardless of search terms.
def SearchIsoHunt(sender):
  dir = MediaContainer()
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"Search all categories","",summary="",thumb=R(ICON),art=R(ART)),category=99))
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"Movies","",summary=None,thumb=R(ICON),art=R(ART)),category=1))
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"Audio","",summary=None,thumb=R(ICON),art=R(ART)),category=2))
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"TV Shows","",summary=None,thumb=R(ICON),art=R(ART)),category=3))
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"Games","",summary=None,thumb=R(ICON),art=R(ART)),category=4))
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"Music Video","",summary=None,thumb=R(ICON),art=R(ART)),category=10))
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"Applications","",summary=None,thumb=R(ICON),art=R(ART)),category=5))
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"Pictures","",summary=None,thumb=R(ICON),art=R(ART)),category=7))
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"Comics","",summary=None,thumb=R(ICON),art=R(ART)),category=8))
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"Books","",summary=None,thumb=R(ICON),art=R(ART)),category=9))
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"Miscellaneous","",summary=None,thumb=R(ICON),art=R(ART)),category=0))
  dir.Append(Function(InputDirectoryItem(SearchIsoHuntCategory,"Unclassified","",summary=None,thumb=R(ICON),art=R(ART)),category=11))
  return dir

def SearchIsoHuntCategory(sender, query=None, category=99):
  dir = MediaContainer()
  url = "http://isohunt.com/js/rss"
  if query != None:
    url += "/%s" % query
  if category != 99:
    url += "?iht=%d" % category
  Log(url, True)
  feed = HTML.ElementFromURL(url, errors='ignore').xpath("//item")
  if feed == None:
    return MessageContainer("Error", "Search returned no results")
  if len(feed) == 0:
    return MessageContainer("Error", "No results").ToXML()
  for element in feed:
    title = element.xpath("title")[0].text
    category = element.xpath("category")[0].text
    link = element.find("enclosure").get("url")
    size = prettysize(int(element.find("enclosure").get("length")))
    dir.Append(Function(DirectoryItem(AddTorrent,title,subtitle=None,summary="Category: %s\nSize: %s" % (category,size),thumb=R(ICON),art=R(ART)),torrentUrl=link))
  return dir

# This function was a lot longer in the previous version of the
# Framework. It was so much simpler this time round.
def SearchEZTV(sender, query=None):
  dir = MediaContainer()
  url = "http://ezrss.it/search/index.php?simple&mode=rss&show_name="
  if query != None:
    url += "%s" % query
  Log(url, True)
  feed = HTML.ElementFromURL(url, errors='ignore').xpath("//item")
  if feed == None:
    return MessageContainer("Error", "Search failed")
  if len(feed) == 0:
    return MessageContainer("Error", "No results")
  for element in feed:
    title = element.xpath("title")[0].text
    category = element.xpath("category")[0].text
    link = element.find("enclosure").get("url")
    size = prettysize(int(element.find("enclosure").get("length")))
    dir.Append(Function(DirectoryItem(AddTorrent,title,subtitle=None,summary="Category: %s\nSize: %s" % (category,size),thumb=R(ICON),art=R(ART)),torrentUrl=link))
  return dir

# This is currently unused due to issues between PIL and Framework v1
# re-enable it later if PIL gets included in the framework by sticking this at the top:
# from icon      import TorrentIconCached
# and the rest in a file called icon.py:
# from PMS import *
# from PMS.Objects import *
# from PMS.Shortcuts import *
# from PIL import Image, ImageFont, ImageDraw
# import cStringIO
#
# LargeFont	= ImageFont.truetype("/Library/Fonts/Arial Bold.ttf", 100)
# SmallFont	= ImageFont.truetype("/Library/Fonts/Arial Bold.ttf", 30)
#
# def TorrentIcon(name, status, progress=100):
# 	result	= cStringIO.StringIO()
# 	image	= Image.new("RGBA", (304, 450), (0, 0, 0, 0))
# 	draw	= ImageDraw.Draw(image)
#
#  	Log("name: %s, status: %s" % (name, status), True)
# 	draw.text((1, 1), status, font=LargeFont, fill="black")
# 	draw.text((0, 0),	status,	font=LargeFont, fill="white")
# 	draw.text((1, 131),	name,	font=SmallFont, fill="black")
# 	draw.text((0, 130),	name,	font=SmallFont, fill="white")
#
# 	if progress >= 0:
# 		draw.rectangle( ( 0, 170, 3 * progress, 200 ), fill="white", outline="black")
# 		draw.rectangle( ( 3 * progress,	170, 300, 200 ), fill="#444", outline="black")
#
# 	image.save(result, "PNG")
# 	imagedata=result.getvalue()
# 	return DataObject(data = result.getvalue(), contentType="image/png")
#
# def TorrentIconCached(name, status, progress=100):
# 	# TorrentIconCached(torrent["name"],"%d%%" % progress,progress)
# 	if Data.Exists("%s.png" % progress):
# 		return DataObject(data = Data.Load("%s.png" % progress), contentType="image/png")
# 	else:
# 		return TorrentIcon(name, status, progress)