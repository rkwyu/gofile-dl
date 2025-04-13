import argparse
import logging
import math
import os
from typing import Dict
from pathvalidate import sanitize_filename
import requests
import hashlib
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import List

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(funcName)20s()][%(levelname)-8s]: %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("GoFile")


class ProgressBar:
    def __init__(self, total_bytes: int, total_files: int):
        self.total_bytes = total_bytes
        self.downloaded_bytes = 0
        self.total_files = total_files
        self.downloaded_files = 0
        self.lock = Lock()

    def add_downloaded_bytes(self, bytes: int = 0):
        self.downloaded_bytes += bytes

    def add_downloaded_files(self, number: int = 1):
        self.downloaded_files += number

    def update(self, bytes_downloaded: int):
        with self.lock:
            self.downloaded_bytes += bytes_downloaded
            percentage = int(100 * self.downloaded_bytes / self.total_bytes)
            bar = "█" * (percentage // 4)  # 25 chars wide
            empty = " " * (50 - len(bar))
            mb_done = self.downloaded_bytes / 1024 / 1024
            mb_total = self.total_bytes / 1024 / 1024
            print(f"\r Progress: {bar}{empty} {percentage}% ({mb_done:.1f}MB / {mb_total:.1f}MB) ({self.downloaded_files}/{self.total_files})", end="")
            if self.downloaded_bytes >= self.total_bytes:
                print()


class Job:
    def __init__(self, link: str, file: str):
        self.link = link
        self.file = file
        self.content_length = 0

    def set_content_length(self, content_length: int):
        self.content_length = content_length

    def __str__(self):
        return f"{self.file} ({self.link})"


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

    def execute(self, dir: str, content_id: str = None, url: str = None, password: str = None, worker: int = 1) -> None:
        jobs = self.get_jobs(dir, content_id, url, password)
        self.update_content_length(jobs)
        progress_bar = ProgressBar(sum(job.content_length for job in jobs), len(jobs))

        with ThreadPoolExecutor(max_workers=worker) as executor:
            futures = [executor.submit(self.download, job, progress_bar) for job in jobs]
            for future in as_completed(futures):
                future.result()

    def update_content_length(self, jobs: List[Job]):
        for job in jobs:
            try:
                head = requests.head(job.link, headers={"Cookie": f"accountToken={self.token}"})
                job.set_content_length(int(head.headers.get("Content-Length", 0)))
            except:
                pass

    def get_jobs(self, dir: str, content_id: str = None, url: str = None, password: str = None) -> None:
        jobs = list()
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
                                self.execute(dir=dir, content_id=id, password=password)
                            else:
                                filename = child["name"]
                                file = urllib.parse.unquote(os.path.join(dir, sanitize_filename(filename)))
                                link = urllib.parse.unquote(child["link"])
                                jobs.append(Job(link, file))
                    else:
                        filename = data["data"]["name"]
                        file = urllib.parse.unquote(os.path.join(dir, sanitize_filename(filename)))
                        link = urllib.parse.unquote(data["data"]["link"])
                        jobs.append(Job(link, file))
                else:
                    logger.error(f"invalid password: {data['data'].get('passwordStatus')}")
        elif url is not None:
            if url.startswith("https://gofile.io/d/"):
                jobs = self.get_jobs(dir=dir, content_id=url.split("/")[-1], password=password)
            else:
                logger.error(f"invalid url: {url}")
        else:
            logger.error(f"invalid parameters")
        return jobs

    def download(self, job: Job, progress_bar: ProgressBar, chunk_size: int = 8192):
        link = job.link
        file = job.file
        temp = file + ".part"
        try:
            dir = os.path.dirname(file)
            if not os.path.exists(dir):
                os.makedirs(dir)
            if not os.path.exists(file):
                size = os.path.getsize(temp) if os.path.exists(temp) else 0
                progress_bar.add_downloaded_bytes(size)
                with requests.get(
                    link, headers={
                        "Cookie": f"accountToken={self.token}",
                        "Range": f"bytes={size}-"
                    }, stream=True
                ) as r:
                    r.raise_for_status()
                    with open(temp, "ab") as f:
                        for chunk in r.iter_content(chunk_size=chunk_size):
                            f.write(chunk)
                            progress_bar.update(len(chunk))
                    os.rename(temp, file)
                    progress_bar.add_downloaded_files()
        except Exception as e:
            logger.error(f"failed to download ({e}): {file} ({link})")
            if os.path.exists(temp):
                os.remove(temp)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("-w", type=int, dest="worker", help="number of workers / threads")
    parser.add_argument("-d", type=str, dest="dir", help="output directory")
    parser.add_argument("-p", type=str, dest="password", help="password")
    args = parser.parse_args()
    worker = args.worker if args.worker is not None else 1
    dir = args.dir if args.dir is not None else "./output"
    GoFile().execute(dir=dir, url=args.url, password=args.password, worker=worker)
