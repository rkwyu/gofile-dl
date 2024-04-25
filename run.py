import argparse
import logging
import math
import os
from typing import Dict
from pathvalidate import sanitize_filename
import requests

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(funcName)20s()][%(levelname)-8s]: %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("GoFile")


class ProgressBar:
    def __init__(self, name: str, cur: int, total: int) -> None:
        self.reset(name, cur, total)

    def reset(self, name: str, cur: int, total: int):
        self.name = name
        self.cur = cur
        self.total = total

    def print(self):
        self.cur += 1
        if self.cur <= self.total:
            percentage = int(100 * self.cur // self.total)
            fill = "█" * percentage
            empty = " " * (100 - percentage)
            print(f"\r {self.name}: {fill}{empty} {percentage}%", end="\r")
        if self.cur == self.total:
            print()


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

    def update_token(self) -> None:
        if self.token == "":
            data = requests.post("https://api.gofile.io/accounts").json()
            if data["status"] == "ok":
                self.token = data["data"]["token"]
                logger.info(f"updated token: {self.token}")

    def update_wt(self) -> None:
        if self.wt == "":
            alljs = requests.get("https://gofile.io/dist/js/alljs.js").text
            if 'wt: "' in alljs:
                self.wt = alljs.split('wt: "')[1].split('"')[0]
                logger.info(f"updated wt: {self.wt}")

    def execute(self, dir: str, content_id: str = None, url: str = None) -> None:
        if content_id is not None:
            self.update_token()
            self.update_wt()
            data = requests.get(
                f"https://api.gofile.io/contents/{content_id}?wt={self.wt}&cache=true",
                headers={
                    "Authorization": "Bearer " + self.token,
                },
            ).json()
            if data["status"] == "ok":
                if data["data"]["type"] == "folder":
                    dirname = data["data"]["name"]
                    dir = os.path.join(dir, sanitize_filename(dirname))
                    for children_id in data["data"]["childrenIds"]:
                        if data["data"]["children"][children_id]["type"] == "folder":
                            self.execute(dir=dir, content_id=children_id)
                        else:
                            filename = data["data"]["children"][children_id]["name"]
                            file = os.path.join(dir, sanitize_filename(filename))
                            link = data["data"]["children"][children_id]["link"]
                            self.download(link, file)
                else:
                    filename = data["data"]["name"]
                    file = os.path.join(dir, sanitize_filename(filename))
                    link = data["data"]["link"]
                    self.download(link, file)
        elif url is not None:
            if url.startswith("https://gofile.io/d/"):
                self.execute(dir=dir, content_id=url.split("/")[-1])
            else:
                logger.error(f"invalid url: {url}")
        else:
            logger.error(f"invalid parameters")

    def download(self, link: str, file: str, chunk_size: int = 8192):
        try:
            dir = os.path.dirname(file)
            if not os.path.exists(dir):
                os.makedirs(dir)
            if not os.path.exists(file):
                with requests.get(
                    link, headers={"Cookie": "accountToken=" + self.token}, stream=True
                ) as r:
                    r.raise_for_status()
                    with open(file, "wb") as f:
                        content_length = int(r.headers["Content-Length"])
                        progress_bar = ProgressBar(
                            "Downloading", 0, math.ceil(content_length / chunk_size)
                        )
                        for chunk in r.iter_content(chunk_size=chunk_size):
                            f.write(chunk)
                            progress_bar.print()
                    logger.info(f"downloaded: {file} ({link})")
        except Exception as e:
            logger.error(f"failed to download ({e}): {file} ({link})")


parser = argparse.ArgumentParser()
parser.add_argument("url")
parser.add_argument("-d", type=str, dest="dir", help="output directory")
args = parser.parse_args()
if __name__ == "__main__":
    dir = args.dir if args.dir is not None else "./output"
    GoFile().execute(dir=dir, url=args.url)
