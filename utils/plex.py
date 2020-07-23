import time
import requests
import requests.exceptions

from plexapi.video import Show
from plexapi.library import MovieSection
from plexapi.library import ShowSection
from classes.plex import Plex
from utils.base import *


def load_plex_data(server, plex_sections, plexlibrary):
    for sectionid in giefbar(plex_sections.values(), f'{timeoutput()} - Loading data from Plex'):
        section = server.library.sectionByID(sectionid)
        Show._include = ""
        media = section.all()
        items = list()
        for row in giefbar(media, f'{timeoutput()} - Loading Plex section {section.title} (ID {sectionid})'):
            items.append(Plex(row.locations[0], row.guid, row.ratingKey, row.title))
        plexlibrary[sectionid] = items


def check_duplicate(server, plex_sections, config, delay):
    duplicate = 0

    for sectionid, mediatype in giefbar(plex_sections.items(), f'{timeoutput()} - Checking for duplicate in Plex'):
        section = server.library.sectionByID(str(sectionid))
        if isinstance(section, MovieSection):
            for x in section.search(libtype="movie", duplicate=True):
                duplicate += 1
                plex_split(x.ratingKey, config, delay)
                time.sleep(delay)

        if isinstance(section, ShowSection):
            for x in section.search(libtype="show", duplicate=True):
                if len(x.locations) > 1:
                    duplicate += 1
                    plex_split(x.ratingKey, config, delay)
                    time.sleep(delay)

    return duplicate


def plex_compare_media(arr_plex_match, sonarr, radarr, library, config, delay):
    counter = 0
    for arrtype in arr_plex_match.keys():
        if arrtype == "sonarr":
            agent = "thetvdb"
            arr = sonarr
        if arrtype == "radarr":
            agent = "themoviedb"
            arr = radarr
        for arrinstance in arr_plex_match[arrtype].keys():
            if len(arrinstance) == 0:
                continue
            for folder in arr_plex_match[arrtype][arrinstance].values():
                for items in giefbar(arr[arrinstance], f'{timeoutput()} - Checking Plex against {arrinstance}'):
                    for plex_items in library[folder.get("plex_library_id")]:
                        if items.path == map_path(config, plex_items.fullpath):
                            if plex_items.agent == "imdb":
                                if items.imdb == plex_items.id:
                                    break
                                else:
                                    tqdm.write(
                                        f"{timeoutput()} - Plex metadata item {plex_items.metadataid} with imdb ID:{plex_items.id} did not match {arrinstance} imdb ID:{items.imdb}")

                                    try:
                                        plex_match(config["plex_url"],
                                                   config["plex_token"],
                                                   agent,
                                                   plex_items.metadataid,
                                                   items.imdb,
                                                   items.title,
                                                   delay)

                                        plex_refresh(config["plex_url"],
                                                     config["plex_token"],
                                                     plex_items.metadataid,
                                                     delay)

                                        time.sleep(delay)
                                    except TypeError:
                                        tqdm.write(f"{timeoutput()} - Plex metadata ID appears to be missing.")
                                    counter += 1

                            else:
                                if items.id == plex_items.id:
                                    break
                                else:
                                    tqdm.write(f"{timeoutput()} - Plex metadata item {plex_items.metadataid} with {agent} ID:{plex_items.id} did not match {arrinstance} {agent} ID:{items.id}")

                                    try:
                                        plex_match(config["plex_url"],
                                                   config["plex_token"],
                                                   agent,
                                                   plex_items.metadataid,
                                                   items.id,
                                                   items.title,
                                                   delay)

                                        plex_refresh(config["plex_url"],
                                                     config["plex_token"],
                                                     plex_items.metadataid,
                                                     delay)

                                        time.sleep(delay)
                                    except TypeError:
                                        tqdm.write(f"{timeoutput()} - Plex metadata ID appears to be missing.")
                                    counter += 1
                                break
    return counter


# TODO add ability to use different language codes
def plex_match(url, token, agent, metadataid, agentid, title, delay):
    retries = 5
    while retries > 0:
        try:
            url_params = {
                'X-Plex-Token': token,
                'guid': 'com.plexapp.agents.{}://{}?lang=en'.format(agent, agentid),
                'name': title,
            }
            url_str = '%s/library/metadata/%d/match' % (url, int(metadataid))
            resp = requests.put(url_str, params=url_params, timeout=30)

            if resp.status_code == 200:
                tqdm.write(f"{timeoutput()} - Successfully matched {int(metadataid)} to {title} ({agentid})")
            else:
                tqdm.write(
                    f"{timeoutput()} - Failed to match {int(metadataid)} to {title} ({agentid}) - Plex returned error: {resp.text}")
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout):
            tqdm.write(
                f"{timeoutput()} - Exception matching {int(metadataid)} to {title} ({agentid}) - {retries} left.")
            retries -= 1
            time.sleep(delay)
    if retries == 0:
        raise Exception(
            f"{timeoutput()} - Exception matching {int(metadataid)} to {title} ({agentid}) - Ran out of retries.")


def plex_refresh(url, token, metadataid, delay):
    retries = 5
    while retries > 0:
        try:
            url_params = {
                'X-Plex-Token': token
            }
            url_str = '%s/library/metadata/%d/refresh' % (url, int(metadataid))
            resp = requests.put(url_str, params=url_params, timeout=30)

            if resp.status_code == 200:
                tqdm.write(f"{timeoutput()} - Successfully refreshed {int(metadataid)}")
            else:
                tqdm.write(f"{timeoutput()} - Failed refreshing {int(metadataid)} - Plex returned error: {resp.text}")
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout):
            tqdm.write(f"{timeoutput()} - Exception refreshing {int(metadataid)} - {retries} left.")
            retries -= 1
            time.sleep(delay)
    if retries == 0:
        raise Exception(f"{timeoutput()} - Exception refreshing {int(metadataid)} - Ran out of retries.")


def plex_split(metadataid, config, delay):
    retries = 5
    while retries > 0:
        try:
            tqdm.write(f"{timeoutput()} - Checking for duplicate in Plex: Splitting item with ID:{metadataid}")
            url_params = {
                'X-Plex-Token': config["plex_token"]
            }
            url_str = '%s/library/metadata/%d/split' % (config["plex_url"], metadataid)
            resp = requests.put(url_str, params=url_params, timeout=30)

            if resp.status_code == 200:
                tqdm.write(f"{timeoutput()} - Checking for duplicate in Plex: Successfully split {metadataid}.")
            else:
                tqdm.write(f"{timeoutput()} - Checking for duplicate in Plex: Failed to split {metadataid} - Plex returned error: {resp.text}")
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectTimeout):
            tqdm.write(
                f"{timeoutput()} - Checking for duplicate in Plex: Exception splitting {metadataid} - {retries} left.")
            retries -= 1
            time.sleep(delay)
    if retries == 0:
        raise Exception(
            f"{timeoutput()} - Checking for duplicate in Plex: Exception splitting {metadataid} - Ran out of retries.")
