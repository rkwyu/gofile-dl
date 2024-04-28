# Gofile-dl [![python](https://img.shields.io/badge/Python-3.11-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)

[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

## About ##
A CLI (Command Line Interface) tool to download all directories and files from a gofile.io link as a batch  

## Setup ##
1. Download repository  
```console
git clone https://github.com/rkwyu/gofile-dl
```
2. Install dependencies
```console
cd ./gofile-dl
python -m pip install -r requirements.txt
```

## Usage (CLI) ##
```console
usage: run.py [-h] [-d DIR] url

positional arguments:
  url

options:
  -h, --help  show this help message and exit
  -d DIR      output directory
```
Default output directory is `./output` 

#### Example 1: Download files from https://gofile.io/d/foobar ####
```console
python run.py https://gofile.io/d/foobar
```

#### Example 2: Download files from https://gofile.io/d/foobar to directory /baz/qux ####
```console
python run.py -d /baz/qux https://gofile.io/d/foobar
```

## License ##
[GNU GPL v3.0](LICENSE.md)
