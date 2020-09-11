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

MEDIA_URL = 'https://plugin.sc2.zone/api/media/filter/{filter_name}?{query}&access_token=9ajdu4xyn1ig8nxsodr3'
MEDIA_DETAIL_URL = 'https://plugin.sc2.zone/api/media/{mediaid}?access_token=9ajdu4xyn1ig8nxsodr3'
MEDIA_SERVICE_URL = 'https://plugin.sc2.zone/api/media/detail/service/{service}/{id}?access_token=9ajdu4xyn1ig8nxsodr3'
STREAM_URL = 'plugin://plugin.video.stream-cinema-2-release/process_media_item/?url=%2Fapi%2Fmedia%2F{mediaid}%2Fstreams&media_id={mediaid}&root_parent_id={root_parent_id}'

ADDON = xbmcaddon.Addon()


def media_detail_url(mediaid):
    return MEDIA_DETAIL_URL.format(mediaid=mediaid)


def media_service_url(service, id):
    return MEDIA_SERVICE_URL.format(service=service, id=id)


def csfd_id_from_nfo(nfo_path):
    file = open(nfo_path, 'r')
    lines = file.readlines()
    file.close()
    csfd_id = ''
    for line in lines:
        item = line.strip()
        index = item.find("film/")
        print('get csfd id, item: {}, index: {}'.format(item, index))
        if index > -1:
            if item.endswith('-'):
                csfd_id = item[:-1]
            csfd_id = csfd_id[index + 5:]
    return csfd_id


def clear_folder(path):
    files = os.listdir(path)
    for file in files:
        filename = os.path.join(path, file)
        if os.path.isfile(filename):
            os.remove(filename)


def write_stream_file(strm_path, content):
    file = xbmcvfs.File(strm_path, 'w')
    file.write(str(content))
    file.close()


def write_nfo_file(name, media_id, type):
    url = media_detail_url(media_id)
    detail_contents = ''
    try:
        detail_contents = urllib2.urlopen(url).read()
        time.sleep(1)
    except HTTPError as err:
        print(err)
    if detail_contents != '':
        media_detail = json.loads(detail_contents)
        if 'services' in media_detail:
            services = media_detail['services']
            if (os.path.exists(name)):
                os.remove(name)
            file = xbmcvfs.File(name, 'w')
            if 'csfd' in services:
                csfdId = services['csfd']
                file.write("https://www.csfd.cz/film/{}".format(csfdId) + "\n")
            if 'tmdb' in services:
                tmdbId = services['tmdb']
                file.write("https://www.themoviedb.org/{}/{}".format(type, tmdbId) + "\n")
            if 'imdb' in services:
                imdbId = services['imdb']
                file.write("https://www.imdb.com/title/{}".format(imdbId) + "\n")
            file.close()


def write_result(library_dir, result):
    print(result)
    now = datetime.now()
    result_filename = os.path.join(library_dir, "result_{}.txt".format(now.strftime("%Y%m%d-%H%M%S")))
    result_file = xbmcvfs.File(os.path.join(library_dir, result_filename), 'w')
    for line in result:
        result_file.write(line)
        result_file.write("\n")
    result_file.close()


def convert_movies(mf):
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
    time_estimation = count / 2
    answer = xbmcgui.Dialog().yesno(ADDON.getLocalizedString(30019),
                                    ADDON.getLocalizedString(30020).format(count, time_estimation))
    if not answer:
        return
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON.getLocalizedString(30019), ADDON.getLocalizedString(30021))
    i = 0
    # iterate through list and get csfd id from nfo file inside each folder
    for movie in movies:
        # is it directory
        if not (os.path.isdir(os.path.join(mf, movie))):
            continue
        nfo_path = os.path.join(mf, movie, movie + ".nfo")
        strm_path = os.path.join(mf, movie, movie + ".strm")
        if os.path.isfile(strm_path):
            file = open(strm_path, 'r')
            lines = file.readlines()
            file.close()
            line = lines[0].strip()
            # it is SC1 stream file?
            if line.find("plugin.video.stream-cinema/") > -1:
                if os.path.isfile(nfo_path):
                    csfd_id = csfd_id_from_nfo(nfo_path)
                    print("----- it is SC1 stream file, convert it! CSFD ID: " + csfd_id)

                    # call API service with csfd id and get media_id
                    # back up old strm file
                    # construct SCC stream link and write it to file
                    url = media_service_url('csfd', csfd_id)
                    contents = ''
                    try:
                        contents = urllib2.urlopen(url).read()
                        time.sleep(1)
                    except HTTPError as err:
                        result.append("- Movie {} HTTP error {}".format(movie, err.code))
                    if contents != '':
                        data = json.loads(contents)
                        scc_id = data['_id']
                        # create new strm file for SCC plugin!
                        write_stream_file(strm_path, STREAM_URL.format(mediaid=scc_id, root_parent_id=scc_id))
                        write_nfo_file(nfo_path, scc_id, 'movie')
                        print("=> File {} converted successfully".format(strm_path))
                        result.append("+ Movie {} converted from SC1 format".format(movie))

                else:
                    result.append("- Movie {} cannot be converted from SC1 format, nfo file is missing".format(movie))

            # it is stream URL from SCC release earlier version (prior to 1.3.8)
            elif line.find("plugin.video.stream-cinema-2-release/get_streams/") > -1 and line.find(
                    "plugin.video.stream-cinema-2-release/get_streams/?") == -1:
                index = line.find("streams/")
                scc_id = line[index + 8:]
                # create new stream file for SCC plugin!
                write_stream_file(strm_path, STREAM_URL.format(mediaid=scc_id, root_parent_id=scc_id))
                write_nfo_file(nfo_path, scc_id, 'movie')
                result.append("+ Movie {} converted from earlier version of SCC (prior to 1.3.8)".format(movie))

            # it is stream URL from SCC release earlier version (1.3.8)
            elif line.find("plugin.video.stream-cinema-2-release/get_streams/") > -1:
                # index = line.find("streams/")
                scc_id = line[-24:]
                # create new stream file for SCC plugin!
                write_stream_file(strm_path, STREAM_URL.format(mediaid=scc_id, root_parent_id=scc_id))
                write_nfo_file(nfo_path, scc_id, 'movie')
                result.append("+ Movie {} converted from earlier version of SCC (1.3.8)".format(movie))

            # it is stream URL from SCC beta
            elif line.find("plugin.video.stream-cinema-2/select_stream/") > -1:
                result.append(
                    "- Movie {} cannot be converted from SCC beta version, not supported - media id mismatch".format(
                        movie))

            else:
                result.append("* Movie {} - no conversion needed, already in correct SCC format".format(movie))

        else:
            result.append("- Movie {} cannot be processed, stream file is missing".format(movie))

        # update progress dialog
        i = i + 1
        print("------ UPDATE progress bar... movie number {}/{}, percentage: {}".format(i, count, int(
            100 * float(i) / float(count))))
        dp.update(int(100 * float(i) / float(count)))
        if dp.iscanceled():
            result.append("- Library conversion process canceled by user!")
            break

    # write result to a file in root directory of the library
    dp.close()
    result.append("Library conversion end: {}".format(now.strftime("%Y%m%d-%H%M%S")))
    write_result(mf, result)


def convert_tvshows(tf):
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
    time_estimation = count * 5
    answer = xbmcgui.Dialog().yesno(ADDON.getLocalizedString(30019),
                                    ADDON.getLocalizedString(30022).format(count, time_estimation))
    if not answer:
        return
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON.getLocalizedString(30019), ADDON.getLocalizedString(30021))
    i = 0
    # iterate through list and get csfd id from nfo file inside each folder
    for tvshow in tvshows:
        # is it directory
        if not (os.path.isdir(os.path.join(tf, tvshow))):
            continue
        nfo_path = os.path.join(tf, tvshow, tvshow + ".nfo")
        tvshow_path = os.path.join(tf, tvshow)
        if not (os.path.exists(nfo_path)):
            nfo_path = os.path.join(tvshow_path, "tvshow.nfo")
        # get first episode of the first season
        # and from this episode find stream file format
        seasons = os.listdir(tvshow_path)
        first_season = ''
        for item in seasons:
            if os.path.isdir(os.path.join(tvshow_path, item)):
                first_season = os.path.join(tvshow_path, item)
                break

        if not first_season:
            result.append("- TV show {} cannot be converted, empty directory.".format(tvshow))
            continue

        episodes = os.listdir(first_season)
        first_episode = ''
        for item in episodes:
            if os.path.isfile(os.path.join(first_season, item)) and (item.endswith(".strm")):
                first_episode = os.path.join(first_season, item)
                break

        strm_path = first_episode
        # read stream file of first episode to find whether it is SC1 or SCC
        file = open(strm_path, 'r')
        lines = file.readlines()
        file.close()
        line = lines[0].strip()

        # is it SC1 stream file?
        if line.find("plugin.video.stream-cinema/") > -1:
            if os.path.isfile(nfo_path):
                convert_result = False
                csfd_id = csfd_id_from_nfo(nfo_path)
                print("----- it is SC1 type TV show, convert it! CSFD ID: " + csfd_id)
                url = media_service_url('csfd', csfd_id)
                print('calling url: {}'.format(url))
                contents = ''
                try:
                    contents = urllib2.urlopen(url).read()
                    time.sleep(1)
                except HTTPError as err:
                    result.append("- TV show {} HTTP error {}".format(tvshow, err.code))
                print('result from server: {}'.format(contents))
                if contents != '':
                    data = json.loads(contents)
                    tvshow_id = data['_id']
                    url = MEDIA_URL.format(filter_name="parent", query="value=" + tvshow_id + "&sort=episode")
                    tvshow_contents = ''
                    try:
                        tvshow_contents = urllib2.urlopen(url).read()
                        time.sleep(1)
                    except HTTPError as err:
                        result.append("- TV show {} HTTP error {}".format(tvshow, err.code))
                    if tvshow_contents != '':
                        seasons = json.loads(tvshow_contents)['data']
                        if len(seasons) == 0:
                            result.append("- TV show {} cannot be converted, not found in SCC.".format(tvshow))
                            continue
                        if os.path.isfile(os.path.join(tf, tvshow, 'tvshow.nfo')):
                            os.remove(os.path.join(tf, tvshow, 'tvshow.nfo'))
                        write_nfo_file(os.path.join(tf, tvshow, tvshow + '.nfo'), tvshow_id, 'tv')
                        clear = False
                        for season in seasons:
                            episode_no = season['_source']['info_labels']['episode']
                            if episode_no != 0:
                                season_dirname = os.path.join(tvshow_path, "Season 01")
                                if not clear:
                                    if os.path.isdir(season_dirname):
                                        clear_folder(season_dirname)
                                        clear = True
                                    else:
                                        xbmcvfs.mkdir(season_dirname)
                                episode_id = season['_id']
                                parent_id = season['_source']['root_parent']
                                season_no = season['_source']['info_labels']['season']
                                episode_no = season['_source']['info_labels']['episode']
                                episode_filename = "S{}E{}.strm".format(str(season_no).zfill(2),
                                                                        str(episode_no).zfill(2))
                                episode_url = STREAM_URL.format(mediaid=episode_id, root_parent_id=parent_id)
                                write_stream_file(os.path.join(season_dirname, episode_filename), episode_url)
                                convert_result = True

                            else:
                                season_no = season['_source']['info_labels']['season']
                                current_season = "Season {}".format(str(season_no).zfill(2))
                                season_id = season["_id"]
                                season_dirname = os.path.join(tvshow_path, current_season)
                                if os.path.isdir(season_dirname):
                                    clear_folder(season_dirname)
                                else:
                                    xbmcvfs.mkdir(season_dirname)

                                url = MEDIA_URL.format(filter_name="parent",
                                                       query="value=" + season_id + "&sort=episode")
                                episodes_contents = ''
                                try:
                                    episodes_contents = urllib2.urlopen(url).read()
                                    time.sleep(1)
                                except HTTPError as err:
                                    result.append("- TV show {} HTTP error {}".format(tvshow, err.code))
                                if episodes_contents != '':
                                    episodes_data = json.loads(episodes_contents)
                                    episodes = episodes_data['data']
                                    # episodesCount = episodes_data['totalCount']
                                    # e = 1
                                    for episode in episodes:
                                        season_no = episode['_source']['info_labels']['season']
                                        episode_no = episode['_source']['info_labels']['episode']
                                        episode_filename = "S{}E{}.strm".format(str(season_no).zfill(2),
                                                                                str(episode_no).zfill(2))
                                        episode_id = episode['_id']
                                        episode_url = STREAM_URL.format(mediaid=episode_id, root_parent_id=season_id)
                                        write_stream_file(os.path.join(season_dirname, episode_filename), episode_url)
                                        convert_result = True

                if convert_result:
                    result.append("+ TV show {} converted from SC1 format".format(tvshow))

            else:
                result.append("- TV show {} cannot be converted from SC1 format, nfo file is missing".format(tvshow))

        else:
            result.append("* TV show {} - no conversion needed, already in correct SCC format".format(tvshow))

        # update progress dialog
        i = i + 1
        print("------ UPDATE progress bar... TV Show number {}/{}, percentage: {}"
              .format(i, count, int(100 * float(i) / float(count))))
        dp.update(int(100 * float(i) / float(count)))

        if dp.iscanceled():
            result.append("- Library conversion process canceled by user!")
            break

    # write result to a file in root directory of the library
    dp.close()
    now = datetime.now()
    result.append("Library conversion end: {}".format(now.strftime("%Y%m%d-%H%M%S")))
    write_result(tf, result)


def convert_library():
    print("++++++++++ in convertLibrary")
    if ADDON.getSetting("movie_folder") == '':
        xbmcgui.Dialog().notification(ADDON.getLocalizedString(30015),
                                      ADDON.getLocalizedString(30016),
                                      icon=xbmcgui.NOTIFICATION_WARNING,
                                      time=5000)
        ADDON.openSettings()
    mf = ADDON.getSetting("movie_folder")
    if mf != '':
        convert_movies(mf)

    if ADDON.getSetting("tvshow_Folder") == '':
        xbmcgui.Dialog().notification(ADDON.getLocalizedString(30015),
                                      ADDON.getLocalizedString(30017),
                                      icon=xbmcgui.NOTIFICATION_WARNING,
                                      time=5000)
        ADDON.openSettings()
    tf = ADDON.getSetting("tvshow_folder")
    if tf != '':
        convert_tvshows(tf)

    xbmc.executebuiltin('UpdateLibrary(video)')


convert_library()
