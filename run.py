import argparse
import fnmatch
import hashlib
import logging
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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

CHUNK_SIZE = 65536
REQUEST_TIMEOUT = 30
DOWNLOAD_TIMEOUT = (10, 60)


def _create_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _display_name(dest: str) -> str:
    basename = os.path.basename(dest)
    if len(basename) > 25:
        return basename[:10] + "....." + basename[-10:]
    return basename.rjust(25)


class File:
    def __init__(self, link: str, dest: str, size: int):
        self.size = size
        self.link = link
        self.dest = dest

    def __str__(self):
        return f"{self.dest} ({self.link})"


class Downloader:
    def __init__(self, token):
        self.token = token
        self.progress_lock = Lock()
        self.progress_bar = None
        self.session = _create_session()

    def _download_range(self, link, start, end, temp_file, i):
        existing_size = os.path.getsize(temp_file) if os.path.exists(temp_file) else 0
        range_start = start + existing_size
        if range_start > end:
            return i
        headers = {
            "Cookie": f"accountToken={self.token}",
            "Range": f"bytes={range_start}-{end}"
        }
        with self.session.get(link, headers=headers, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
            r.raise_for_status()
            with open(temp_file, "ab") as f:
                for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        with self.progress_lock:
                            self.progress_bar.update(len(chunk))
        return i

    def _merge_temp_files(self, temp_dir, dest, num_threads):
        with open(dest, "wb") as outfile:
            for i in range(num_threads):
                temp_file = os.path.join(temp_dir, f"part_{i}")
                with open(temp_file, "rb") as f:
                    shutil.copyfileobj(f, outfile)
                os.remove(temp_file)
        shutil.rmtree(temp_dir)

    def download(self, file: File, num_threads=4):
        total_size = file.size
        link = file.link
        dest = file.dest
        temp_dir = dest + "_parts"
        try:
            if os.path.exists(dest):
                if os.path.getsize(dest) == total_size:
                    return

            display_name = _display_name(dest)

            if num_threads == 1:
                temp_file = dest + ".part"
                downloaded_bytes = os.path.getsize(temp_file) if os.path.exists(temp_file) else 0

                self.progress_bar = tqdm(total=total_size, initial=downloaded_bytes, unit='B', unit_scale=True, desc=f'Downloading {display_name}')

                headers = {
                    "Cookie": f"accountToken={self.token}",
                    "Range": f"bytes={downloaded_bytes}-"
                }
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with self.session.get(link, headers=headers, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
                    r.raise_for_status()
                    with open(temp_file, "ab") as f:
                        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                            if chunk:
                                f.write(chunk)
                                self.progress_bar.update(len(chunk))

                self.progress_bar.close()
                os.rename(temp_file, dest)
            else:
                if os.path.exists(dest + ".part"):
                    os.remove(dest + ".part")

                check_file = os.path.join(temp_dir, "num_threads")
                if os.path.exists(temp_dir):
                    prev_num_threads = None
                    if os.path.exists(check_file):
                        with open(check_file) as f:
                            prev_num_threads = int(f.read())
                    if prev_num_threads is None or prev_num_threads != num_threads:
                        shutil.rmtree(temp_dir)

                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir, exist_ok=True)
                    with open(check_file, "w") as f:
                        f.write(str(num_threads))

                part_size = math.ceil(total_size / num_threads)

                downloaded_bytes = 0
                for i in range(num_threads):
                    part_file = os.path.join(temp_dir, f"part_{i}")
                    if os.path.exists(part_file):
                        downloaded_bytes += os.path.getsize(part_file)

                self.progress_bar = tqdm(total=total_size, initial=downloaded_bytes, unit='B', unit_scale=True, desc=f'Downloading {display_name}')

                futures = []
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
                    for i in range(num_threads):
                        start = i * part_size
                        end = min(start + part_size - 1, total_size - 1)
                        temp_file = os.path.join(temp_dir, f"part_{i}")
                        futures.append(executor.submit(self._download_range, link, start, end, temp_file, i))
                    for future in as_completed(futures):
                        future.result()

                self.progress_bar.close()
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
        self.xwt = ""
        self.lock = Lock()
        self.xbl = "en"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
        self.session = _create_session()

    def update_token(self, force: bool = False) -> None:
        if self.token == "" or force:
            data = self.session.post("https://api.gofile.io/accounts", timeout=REQUEST_TIMEOUT).json()
            if data["status"] == "ok":
                self.token = data["data"]["token"]

                time_slot = int(time.time()) // 14400
                raw = f"{self.user_agent}::{self.xbl}::{self.token}::{time_slot}::5d4f7g8sd45fsd"
                self.xwt = hashlib.sha256(raw.encode()).hexdigest()
                logger.info(f"updated xwt: {self.xwt}")

                logger.info(f"updated token: {self.token}")
            else:
                raise Exception("cannot get token")

    def execute(
        self,
        output_dir: str,
        content_id: str = None,
        url: str = None,
        password: str = None,
        proxy: str = None,
        num_threads: int = 1,
        includes: list[str] = None,
        excludes: list[str] = None) -> None:
        if proxy is not None:
            logger.info(f"Proxy set to: {proxy}")
            os.environ['HTTP_PROXY'] = proxy
            os.environ['HTTPS_PROXY'] = proxy
        else:
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)

        files = self.get_files(output_dir, content_id, url, password, includes, excludes)
        downloader = Downloader(token=self.token)
        for file in files:
            downloader.download(file, num_threads=num_threads)

    def is_included(self, filename: str, includes: list[str]) -> bool:
        if len(includes) == 0:
            return True
        return any(fnmatch.fnmatch(filename, pattern) for pattern in includes)

    def is_excluded(self, filename: str, excludes: list[str]) -> bool:
        if len(excludes) == 0:
            return False
        return any(fnmatch.fnmatch(filename, pattern) for pattern in excludes)

    def _fetch_content(self, content_id: str) -> dict:
        for attempt in range(2):
            data = self.session.get(
                f"https://api.gofile.io/contents/{content_id}",
                headers={
                    'User-Agent': self.user_agent,
                    "Authorization": "Bearer " + self.token,
                    'X-BL': self.xbl,
                    "X-Website-Token": self.xwt,
                },
                timeout=REQUEST_TIMEOUT,
            ).json()
            if data["status"] == "ok":
                return data
            if attempt == 0:
                logger.warning(f"API error (status={data['status']}), refreshing token and retrying")
                self.update_token(force=True)
        return data

    def get_files(
            self, output_dir: str,
            content_id: str = None,
            url: str = None,
            password: str = None,
            includes: list[str] = None,
            excludes: list[str] = None) -> list[File]:
        if includes is None:
            includes = []
        if excludes is None:
            excludes = []
        files = list()
        if content_id is not None:
            self.update_token()
            data = self._fetch_content(content_id)
            if data["status"] == "ok":
                if data["data"].get("passwordStatus", "passwordOk") == "passwordOk":
                    if data["data"]["type"] == "folder":
                        dirname = data["data"]["name"]
                        output_dir = os.path.join(output_dir, sanitize_filename(dirname))
                        for (id, child) in data["data"]["children"].items():
                            if child["type"] == "folder":
                                folder_files = self.get_files(output_dir=output_dir, content_id=id, password=password, includes=includes, excludes=excludes)
                                files.extend(folder_files)
                            else:
                                filename = child["name"]
                                if self.is_included(filename, includes) and not self.is_excluded(filename, excludes):
                                    files.append(File(
                                        size=child["size"],
                                        link=child["link"],
                                        dest=os.path.join(output_dir, sanitize_filename(filename))))
                    else:
                        filename = data["data"]["name"]
                        if self.is_included(filename, includes) and not self.is_excluded(filename, excludes):
                            files.append(File(
                                size=data["data"]["size"],
                                link=data["data"]["link"],
                                dest=os.path.join(output_dir, sanitize_filename(filename))))
                else:
                    logger.error(f"invalid password: {data['data'].get('passwordStatus')}")
            else:
                logger.error(f"API request failed for content {content_id}: {data.get('status')}")
        elif url is not None:
            if url.startswith("https://gofile.io/d/"):
                files = self.get_files(output_dir=output_dir, content_id=url.split("/")[-1], password=password, includes=includes, excludes=excludes)
            else:
                logger.error(f"invalid url: {url}")
        else:
            logger.error(f"invalid parameters")
        return files

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("url", nargs='?', default=None, help="url to process (if not using -f)")
    group.add_argument("-f", type=str, dest="file", help="local file to process")
    parser.add_argument("-t", type=int, dest="num_threads", help="number of threads (default: 1)")
    parser.add_argument("-d", type=str, dest="dir", help="output directory")
    parser.add_argument("-p", type=str, dest="password", help="password")
    parser.add_argument("-x", type=str, dest="proxy", help="proxy server (format: ip/host:port)")
    parser.add_argument("-i", action="append", dest="includes", help="included files (supporting wildcard *)")
    parser.add_argument("-e", action="append", dest="excludes", help="excluded files (supporting wildcard *)")
    args = parser.parse_args()
    num_threads = args.num_threads if args.num_threads is not None else 1
    output_dir = args.dir if args.dir is not None else "./output"
    if args.file is not None:
        if os.path.exists(args.file):
            with open(args.file) as f:
                for line in f:
                    line = line.strip()
                    if line == "" or line.startswith("#"):
                        continue
                    GoFile().execute(
                        output_dir=output_dir,
                        url=line,
                        password=args.password,
                        proxy=args.proxy,
                        num_threads=num_threads,
                        includes=args.includes,
                        excludes=args.excludes)
        else:
            logger.error(f"file not found: {args.file}")
    else:
        GoFile().execute(
            output_dir=output_dir,
            url=args.url,
            password=args.password,
            proxy=args.proxy,
            num_threads=num_threads,
            includes=args.includes,
            excludes=args.excludes)
