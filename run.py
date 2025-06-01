import argparse
import fnmatch
import hashlib
import logging
import math
import os
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import requests
from pathvalidate import sanitize_filename
import shutil
from tqdm import tqdm


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(funcName)20s()][%(levelname)-8s]: %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("GoFile")


class File:
    def __init__(self, link: str, dest: str):
        self.link = link
        self.dest = dest

    def __str__(self):
        return f"{self.dest} ({self.link})"


class Downloader:
    def __init__(self, token):
        self.token = token
        self.progress_lock = Lock()
        self.progress_bar = None

    # send HEAD request to get the file size, and check if the site supports range
    def _get_total_size(self, link):
        r = requests.head(link, headers={"Cookie": f"accountToken={self.token}"})
        r.raise_for_status()
        return int(r.headers["Content-Length"]), r.headers.get("Accept-Ranges", "none") == "bytes"

    # download the range of the file
    def _download_range(self, link, start, end, temp_file, i):
        existing_size = os.path.getsize(temp_file) if os.path.exists(temp_file) else 0
        range_start = start + existing_size
        if range_start > end:
            return i
        headers = {
            "Cookie": f"accountToken={self.token}",
            "Range": f"bytes={range_start}-{end}"
        }
        with requests.get(link, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(temp_file, "ab") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        with self.progress_lock:
                            self.progress_bar.update(len(chunk))
        return i

    # merge temp files
    def _merge_temp_files(self, temp_dir, dest, num_threads):
        with open(dest, "wb") as outfile:
            for i in range(num_threads):
                temp_file = os.path.join(temp_dir, f"part_{i}")
                with open(temp_file, "rb") as f:
                    outfile.write(f.read())
                os.remove(temp_file)
        shutil.rmtree(temp_dir)

    def download(self, file: File, num_threads=4):
        link = file.link
        dest = file.dest
        temp_dir = dest + "_parts"
        try:
            # get file size, and if the site supports range
            total_size, is_support_range = self._get_total_size(link)

            # skip download if the file has been fully downloaded
            if os.path.exists(dest):
                if os.path.getsize(dest) == total_size:
                    return
            
            if num_threads == 1 or not is_support_range:
                temp_file = dest + ".part"

                # calculate downloaded bytes
                downloaded_bytes = os.path.getsize(temp_file) if os.path.exists(temp_file) else 0

                # start progress bar
                if len(os.path.basename(dest)) > 25:
                    display_name = os.path.basename(dest)[:10] + "....." + os.path.basename(dest)[-10:]
                else:
                    display_name = os.path.basename(dest).rjust(25)
                self.progress_bar = tqdm(total=total_size, initial=downloaded_bytes, unit='B', unit_scale=True, desc=f'Downloading {display_name}')

                # download file
                headers = {
                    "Cookie": f"accountToken={self.token}",
                    "Range": f"bytes={downloaded_bytes}-"
                }
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with requests.get(link, headers=headers, stream=True) as r:
                    r.raise_for_status()
                    with open(temp_file, "ab") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                self.progress_bar.update(len(chunk))

                # close progress bar
                self.progress_bar.close()

                # rename temp file
                os.rename(temp_file, dest)
            else:
                # remove single thread file if it exists
                os.path.exists(dest + ".part") and os.remove(dest + ".part")

                # check if the num_threads is matched
                # remove the previous downloaded temp files if it doesn't match
                check_file = os.path.join(temp_dir, "num_threads")
                if os.path.exists(temp_dir):
                    prev_num_threads = None
                    if os.path.exists(check_file):
                        with open(check_file) as f:
                            prev_num_threads = int(f.read())
                    if prev_num_threads is None or prev_num_threads != num_threads:
                        shutil.rmtree(temp_dir)

                if not os.path.exists(temp_dir):
                    # create temp directory for temp files
                    os.makedirs(temp_dir, exist_ok=True)

                    # add check_file
                    with open(check_file, "w") as f:
                        f.write(str(num_threads))

                # calculate the number of temp files
                part_size = math.ceil(total_size / num_threads)

                # calculate downloaded bytes
                downloaded_bytes = 0
                for i in range(num_threads):
                    part_file = os.path.join(temp_dir, f"part_{i}")
                    if os.path.exists(part_file):
                        downloaded_bytes += os.path.getsize(part_file)

                # start progress bar
                if len(os.path.basename(dest)) > 25:
                    display_name = os.path.basename(dest)[:10] + "....." + os.path.basename(dest)[-10:]
                else:
                    display_name = os.path.basename(dest).rjust(25)
                self.progress_bar = tqdm(total=total_size, initial=downloaded_bytes, unit='B', unit_scale=True, desc=f'Downloading {display_name}')

                # download temp files
                futures = []
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
                    for i in range(num_threads):
                        start = i * part_size
                        end = min(start + part_size - 1, total_size - 1)
                        temp_file = os.path.join(temp_dir, f"part_{i}")
                        futures.append(executor.submit(self._download_range, link, start, end, temp_file, i))
                    for future in as_completed(futures):
                        future.result()

                # close progress bar
                self.progress_bar.close()

                # merge temp files
                self._merge_temp_files(temp_dir, dest, num_threads)
        except Exception as e:
            if self.progress_bar:
                self.progress_bar.close()
            logger.error(f"failed to download ({e}): {dest} ({link})")


class GoFileMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class GoFile(metaclass=GoFileMeta):
    def __init__(self) -> None:
        self.token = ""
        self.wt = ""
        self.lock = Lock()

    def update_token(self) -> None:
        if self.token == "":
            data = requests.post("https://api.gofile.io/accounts").json()
            if data["status"] == "ok":
                self.token = data["data"]["token"]
                logger.info(f"updated token: {self.token}")
            else:
                raise Exception("cannot get token")

    def update_wt(self) -> None:
        if self.wt == "":
            alljs = requests.get("https://gofile.io/dist/js/global.js").text
            if 'appdata.wt = "' in alljs:
                self.wt = alljs.split('appdata.wt = "')[1].split('"')[0]
                logger.info(f"updated wt: {self.wt}")
            else:
                raise Exception("cannot get wt")

    def execute(self, dir: str, content_id: str = None, url: str = None, password: str = None, proxy: str = None, num_threads: int = 1, excludes: list[str] = None) -> None:
        if proxy is not None:
            logger.info(f"Proxy set to: {proxy}")
            os.environ['HTTP_PROXY'] = proxy
            os.environ['HTTPS_PROXY'] = proxy

        files = self.get_files(dir, content_id, url, password, excludes)
        for file in files:
            Downloader(token=self.token).download(file, num_threads=num_threads)

    def get_files(self, dir: str, content_id: str = None, url: str = None, password: str = None, excludes: list[str] = None) -> list[File]:
        if excludes is None:
            excludes = []
        files = list()
        if content_id is not None:
            self.update_token()
            self.update_wt()
            hash_password = hashlib.sha256(password.encode()).hexdigest() if password != None else ""
            data = requests.get(
                f"https://api.gofile.io/contents/{content_id}?wt={self.wt}&cache=true&password={hash_password}",
                headers={
                    "Authorization": "Bearer " + self.token,
                },
            ).json()
            if data["status"] == "ok":
                if data["data"].get("passwordStatus", "passwordOk") == "passwordOk":
                    if data["data"]["type"] == "folder":
                        dirname = data["data"]["name"]
                        dir = os.path.join(dir, sanitize_filename(dirname))
                        for (id, child) in data["data"]["children"].items():
                            if child["type"] == "folder":
                                folder_files = self.get_files(dir=dir, content_id=id, password=password, excludes=excludes)
                                files.extend(folder_files)
                            else:
                                filename = child["name"]
                                if not any(fnmatch.fnmatch(filename, pattern) for pattern in excludes):
                                    files.append(File(
                                        link=urllib.parse.unquote(child["link"]), 
                                        dest=urllib.parse.unquote(os.path.join(dir, sanitize_filename(filename)))))
                    else:
                        filename = data["data"]["name"]
                        if not any(fnmatch.fnmatch(filename, pattern) for pattern in excludes):
                            files.append(File(
                                link=urllib.parse.unquote(data["data"]["link"]), 
                                dest=urllib.parse.unquote(os.path.join(dir, sanitize_filename(filename)))))
                else:
                    logger.error(f"invalid password: {data['data'].get('passwordStatus')}")
        elif url is not None:
            if url.startswith("https://gofile.io/d/"):
                files = self.get_files(dir=dir, content_id=url.split("/")[-1], password=password, excludes=excludes)
            else:
                logger.error(f"invalid url: {url}")
        else:
            logger.error(f"invalid parameters")
        return files

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("-t", type=int, dest="num_threads", help="number of threads")
    parser.add_argument("-d", type=str, dest="dir", help="output directory")
    parser.add_argument("-p", type=str, dest="password", help="password")
    parser.add_argument("-x", type=str, dest="proxy", help="proxy server (ip/host:port)")
    parser.add_argument("-e", action="append", dest="excludes", help="excluded files")
    args = parser.parse_args()
    num_threads = args.num_threads if args.num_threads is not None else 1
    dir = args.dir if args.dir is not None else "./output"
    GoFile().execute(dir=dir, url=args.url, password=args.password, proxy=args.proxy, num_threads=num_threads, excludes=args.excludes)
