import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import os
import urllib2
from urllib2 import HTTPError
import json
from datetime import datetime
import time
import shutil
 
MEDIA_URL = 'https://plugin.sc2.zone/api/media/filter/{filter_name}?{query}&access_token=9ajdu4xyn1ig8nxsodr3'
MEDIA_DETAIL_URL = 'https://plugin.sc2.zone/api/media/{mediaid}?access_token=9ajdu4xyn1ig8nxsodr3'
MEDIA_SERVICE_URL = 'https://plugin.sc2.zone/api/media/detail/service/{service}/{id}?access_token=9ajdu4xyn1ig8nxsodr3'
STREAM_URL = 'plugin://plugin.video.stream-cinema-2-release/process_media_item/?url=%2Fapi%2Fmedia%2F{mediaid}%2Fstreams&media_id={mediaid}&root_parent_id={root_parent_id}'

ADDON = xbmcaddon.Addon()     

def getMediaDetailURL(mediaid):
    return MEDIA_DETAIL_URL.format(mediaid=mediaid)

def getMediaServiceURL(service, id):
    return MEDIA_SERVICE_URL.format(service=service, id=id) 

def getCSFDIdFromNFOFile(nfoPath):
    file = open(nfoPath, 'r') 
    lines = file.readlines()
    file.close()
    csfdId = ''
    for line in lines: 
        item = line.strip()
        index = item.find("film/")
        if(index > -1):
            csfdId = item
            csfdId = csfdId[:-1]
            csfdId = csfdId[index+5:]
    return csfdId

def clearFolder(path):
    files = os.listdir(path)
    for file in files:
        filename = os.path.join(path, file)
        if(os.path.isfile(filename)):
            os.remove(filename)

def writeStreamFile(strmPath, newStrm):
    file = xbmcvfs.File(strmPath, 'w')
    file.write(str(newStrm))
    file.close()

def writeNFOFile(name, id, type):
    url = getMediaDetailURL(id)
    detailContents = ''
    try:
        detailContents = urllib2.urlopen(url).read()
    except HTTPError as err:
        print(err)
    if(detailContents != ''):
        mediaDetail = json.loads(detailContents)
        if('services' in mediaDetail):
            services = mediaDetail['services']
            if(os.path.exists(name)):
                os.remove(name)
            file = xbmcvfs.File(name, 'w')
            if('csfd' in services):
                csfdId = services['csfd'] 
                file.write("https://www.csfd.cz/film/{}".format(csfdId) + "\n")
            if('tmdb' in services):
                tmdbId = services['tmdb']        
                file.write("https://www.themoviedb.org/{}/{}".format(type, tmdbId) + "\n")
            if('imdb' in services):
                imdbId = services['imdb'] 
                file.write("https://www.imdb.com/title/{}".format(imdbId) + "\n")
            file.close()

def convertMovies(mf):
    result = []
    now = datetime.now()
    result.append("Library conversion begin: {}".format(now.strftime("%Y%m%d-%H%M%S")))
    result.append("Movies folder: {}".format(mf))
    print("++++++++++ in convertMovies, mf: " + mf)
    # read content of movies folder
    movies = os.listdir(mf)
    count = 0
    for item in movies:
        if os.path.isdir(os.path.join(mf, item)):
            count = count + 1
    # ask user if he/she really wants to go through movies in library, time estimation
    timeEst = count/2
    # answer = xbmcgui.Dialog().yesno("Library conversion", "This will convert your movie library ({} movies) to the latest version of Stream Cinema Community. Estimated duration is {} seconds. Are you sure you want to run it now?".format(len(movies),timeEst))
    answer = xbmcgui.Dialog().yesno(ADDON.getLocalizedString(30019), ADDON.getLocalizedString(30020).format(count,timeEst))
    if(not(answer)):
        return
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON.getLocalizedString(30019), ADDON.getLocalizedString(30021))
    moviesCount = count
    i = 0; 
    # iterate thru list and get csfd id from nfo file inside each folder
    for movie in movies:
        # is it directory
        if(not(os.path.isdir(os.path.join(mf, movie)))):
            continue
        nfoPath = os.path.join(mf, movie, movie + ".nfo")
        strmPath = os.path.join(mf, movie, movie + ".strm")
        # read strm file (only one line)
        if os.path.isfile(strmPath):
            file = open(strmPath, 'r') 
            lines = file.readlines()
            file.close()
            line = lines[0].strip()        
            # it is SC1 stream file?
            if(line.find("plugin.video.stream-cinema/") > -1):
                if os.path.isfile(nfoPath):
                    csfdId = getCSFDIdFromNFOFile(nfoPath)
                    print("----- it is SC1 stream file, convert it! CSFD ID: " + csfdId)
                    
                    # call API service with csfd id and get mediaid
                    # back up old strm file
                    # construct SC2 strm link and write it to file
                    url = getMediaServiceURL('csfd', csfdId)
                    contents = ''
                    try:
                        contents = urllib2.urlopen(url).read()
                    except HTTPError as err:
                        result.append("- Movie {} HTTP error {}".format(movie, err.code))
                    if(contents != ''):
                        data = json.loads(contents)
                        sc2Id = data['_id']
                        # create new strm file for SC2 plugin!
                        writeStreamFile(strmPath, STREAM_URL.format(mediaid=sc2Id, root_parent_id=sc2Id))
                        writeNFOFile(nfoPath, sc2Id, 'movie')
                        print("=> File {} converted successfuly".format(strmPath))
                        result.append("+ Movie {} converted from SC1 format".format(movie))

                else:
                    result.append("- Movie {} cannot be converted from SC1 format, nfo file is missing".format(movie))

            # it is stream URL from SC2 release earlier version (prior to 1.3.8)
            elif (line.find("plugin.video.stream-cinema-2-release/get_streams/") > -1 and line.find("plugin.video.stream-cinema-2-release/get_streams/?") == -1):
                index = line.find("streams/")
                sc2Id = line[index+8:]
                # create new strm file for SC2 plugin!
                writeStreamFile(strmPath, STREAM_URL.format(mediaid=sc2Id, root_parent_id=sc2Id))
                writeNFOFile(nfoPath, sc2Id, 'movie')
                result.append("+ Movie {} converted from earlier version of SC2 (prior to 1.3.8)".format(movie))
                 
            # it is stream URL from SC2 release earlier version (1.3.8)
            elif (line.find("plugin.video.stream-cinema-2-release/get_streams/") > -1):
                # index = line.find("streams/")
                sc2Id = line[-24:]
                # create new strm file for SC2 plugin!
                writeStreamFile(strmPath, STREAM_URL.format(mediaid=sc2Id, root_parent_id=sc2Id))
                writeNFOFile(nfoPath, sc2Id, 'movie')
                result.append("+ Movie {} converted from earlier version of SC2 (1.3.8)".format(movie))

            # it is stream URL from SC2 beta
            elif (line.find("plugin.video.stream-cinema-2/select_stream/") > -1):
                result.append("- Movie {} cannot be converted from SC2 beta, not supported - media id mismatch".format(movie))
                
            else:
                result.append("* Movie {} - no conversion needed, already in correct SCC format".format(movie))    

                                    
        else:
            result.append("- Movie {} cannot be processed, stream file is missing".format(movie))

        # update progress dialog
        i = i+1
        print("------ UPDATE progress bar... movie number {}/{}, percentage: {}".format(i, moviesCount, int(100*float(i)/float(moviesCount))))
        dp.update(int(100*float(i)/float(moviesCount))) 
        if(dp.iscanceled()):
            result.append("- Library conversion process canceled by user!")            
            break

    # write result to a file in root directory of the library
    dp.close()
    now = datetime.now()
    result.append("Library conversion end: {}".format(now.strftime("%Y%m%d-%H%M%S")))
    resultFileName = os.path.join(mf, "result_{}.txt".format(now.strftime("%Y%m%d-%H%M%S")))
    resultFile = xbmcvfs.File(os.path.join(mf, resultFileName), 'w')
    for line in result:
        resultFile.write(line)
        resultFile.write("\n")
    resultFile.close()

    
def convertOneTVShow(tvshowPath, mediaid):
    return    


def convertTVShows(tf):
    result = []
    now = datetime.now()
    result.append("Library conversion begin: {}".format(now.strftime("%Y%m%d-%H%M%S")))
    result.append("TV Shows folder: {}".format(tf))
    print("++++++++++ in convertTVShows, tf: " + tf)
    # read content of TV Shows folder
    tvshows = os.listdir(tf)
    count = 0
    for item in tvshows:
        if os.path.isdir(os.path.join(tf, item)):
            count = count + 1
    # ask user if he/she really wants to go through TV shows in library, time estimation
    timeEst = count*5
    answer = xbmcgui.Dialog().yesno(ADDON.getLocalizedString(30019), ADDON.getLocalizedString(30022).format(count,timeEst))
    if(not(answer)):
        return
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON.getLocalizedString(30019), ADDON.getLocalizedString(30021))
    tvshowsCount = count
    i = 0; 
    # iterate thru list and get csfd id from nfo file inside each folder
    for tvshow in tvshows:
        # is it directory
        if(not(os.path.isdir(os.path.join(tf, tvshow)))):
            continue
        nfoPath = os.path.join(tf, tvshow, tvshow + ".nfo")
        tvshowPath = os.path.join(tf, tvshow)
        originalTitle = tvshow
        if(not(os.path.exists(nfoPath))):
            nfoPath = os.path.join(tvshowPath, "tvshow.nfo") 
        # get first episode of the first season
        # and from this episode find stream file format
        seasons = os.listdir(tvshowPath)
        firstSeason = ''
        for item in seasons:
            if(os.path.isdir(os.path.join(tvshowPath, item))): 
                firstSeason = os.path.join(tvshowPath, item)
                break
                       
        episodes = os.listdir(os.path.join(firstSeason))
        firstEpisode = ''
        for item in episodes:
            if(os.path.isfile(os.path.join(firstSeason, item)) and (item.endswith(".strm"))):
                firstEpisode = os.path.join(firstSeason, item)
                break
            
        strmPath = firstEpisode
        # read strm file of first episode to find whether it is SC1 or SCC
        # strmPath = os.path.join(tvshowPath, firstSeason, firstEpisode)
        file = open(strmPath, 'r') 
        lines = file.readlines()
        file.close()
        line = lines[0].strip()        

        # is it SC1 stream file?
        if(line.find("plugin.video.stream-cinema/") > -1):
            if os.path.isfile(nfoPath):
                convertResult = False
                csfdId = getCSFDIdFromNFOFile(nfoPath)
                print("----- it is SC1 type TV show, convert it! CSFD ID: " + csfdId)
                # convert!
                url = getMediaServiceURL('csfd', csfdId)
                contents = ''
                try:
                    contents = urllib2.urlopen(url).read()
                except HTTPError as err:
                    result.append("- TV show {} HTTP error {}".format(tvshow, err.code))
                if(contents != ''):
                    data = json.loads(contents)
                    tvshowId = data['_id']
                    url = MEDIA_URL.format(filter_name = "parent", query = "value=" + tvshowId + "&sort=episode")
                    tvShowContents = ''
                    seasonsList = []
                    try:
                        tvShowContents = urllib2.urlopen(url).read()
                    except HTTPError as err:
                        result.append("- TV show {} HTTP error {}".format(tvshow, err.code))
                    if(tvShowContents != ''):
                        seasonData = json.loads(tvShowContents)
                        seasonsCount = seasonData['totalCount']
                        seasons = seasonData['data']
                        clear = False
                        for season in seasons:
                            episodeNo = season['_source']['info_labels']['episode']
                            if(episodeNo != 0):
                                seasonDirName = os.path.join(tvshowPath, "Season 01")
                                if(not(clear)):
                                    if (os.path.isdir(seasonDirName)):
                                        clearFolder(seasonDirName)
                                        clear = True
                                    else:
                                        xbmcvfs.mkdir(seasonDirName)
                                episodeId = season['_id']
                                parentId = season['_source']['root_parent']
                                seasonNo = season['_source']['info_labels']['season']
                                episodeNo = season['_source']['info_labels']['episode']
                                episodeFileName = "S{}E{}.strm".format(str(seasonNo).zfill(2), str(episodeNo).zfill(2))
                                episodeURL = STREAM_URL.format(mediaid=episodeId, root_parent_id=parentId)
                                writeStreamFile(os.path.join(seasonDirName, episodeFileName), episodeURL)
                                convertResult = True
                            
                            else:        
                                seasonNo = season['_source']['info_labels']['season']
                                currentSeason = "Season {}".format(str(seasonNo).zfill(2))
                                seasonId = season["_id"]
                                seasonDirName = os.path.join(tvshowPath, currentSeason)
                                if (os.path.isdir(seasonDirName)):
                                    clearFolder(seasonDirName)
                                else:
                                    xbmcvfs.mkdir(seasonDirName)
                                
                                url = MEDIA_URL.format(filter_name = "parent", query = "value=" + seasonId + "&sort=episode")
                                episodesContents = ''
                                try:
                                    episodesContents = urllib2.urlopen(url).read()
                                except HTTPError as err:
                                    result.append("- TV show {} HTTP error {}".format(tvshow, err.code))
                                if(episodesContents != ''):
                                    episodesData = json.loads(episodesContents) 
                                    episodes = episodesData['data']
                                    episodesCount = episodesData['totalCount']
                                    # e = 1
                                    for episode in episodes:
                                        seasonNo = episode['_source']['info_labels']['season']
                                        episodeNo = episode['_source']['info_labels']['episode']
                                        episodeFileName = "S{}E{}.strm".format(str(seasonNo).zfill(2), str(episodeNo).zfill(2))
                                        episodeId = episode['_id']
                                        episodeURL = STREAM_URL.format(mediaid=episodeId, root_parent_id=seasonId)
                                        writeStreamFile(os.path.join(seasonDirName, episodeFileName), episodeURL)
                                        convertResult = True

                if (convertResult == True):
                    result.append("+ TV show {} converted from SC1 format".format(tvshow))

            else:
                result.append("- TV show {} cannot be converted from SC1 format, nfo file is missing".format(tvshow))

        else:
            result.append("* TV show {} - no conversion needed, already in correct SCC format".format(tvshow))    

        # update progress dialog
        i = i+1
        print("------ UPDATE progress bar... TV Show number {}/{}, percentage: {}".format(i, tvshowsCount, int(100*float(i)/float(tvshowsCount))))
        dp.update(int(100*float(i)/float(tvshowsCount)))
        time.sleep(1)
        
        if(dp.iscanceled()):
            result.append("- Library conversion process canceled by user!")            
            break

    # write result to a file in root directory of the library
    dp.close()
    now = datetime.now()
    result.append("Library conversion end: {}".format(now.strftime("%Y%m%d-%H%M%S")))
    resultFileName = os.path.join(tf, "result_{}.txt".format(now.strftime("%Y%m%d-%H%M%S")))
    print(result)
    resultFile = xbmcvfs.File(os.path.join(tf, resultFileName), 'w')
    for line in result:
        resultFile.write(line)
        resultFile.write("\n")
    resultFile.close()


def convertLibrary():
    print("++++++++++ in convertLibrary")
    if ADDON.getSetting("movie_folder") == '':
        xbmcgui.Dialog().notification(ADDON.getLocalizedString(30015), ADDON.getLocalizedString(30016), icon=xbmcgui.NOTIFICATION_WARNING, time=5000)
        ADDON.openSettings()
    mf = ADDON.getSetting("movie_folder")
    if(mf != ''):
        convertMovies(mf)        

    if ADDON.getSetting("tvshow_Folder") == '':
        xbmcgui.Dialog().notification(ADDON.getLocalizedString(30015), ADDON.getLocalizedString(30017), icon=xbmcgui.NOTIFICATION_WARNING, time=5000)
        ADDON.openSettings()
    tf = ADDON.getSetting("tvshow_Folder")
    if tf != '':
        convertTVShows(tf)
    
    xbmc.executebuiltin('UpdateLibrary(video)')
       

convertLibrary()
