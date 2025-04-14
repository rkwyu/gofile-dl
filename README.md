# Gofile-dl [![python](https://img.shields.io/badge/Python-3.11-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org) 

<a href="https://buymeacoffee.com/r1y5i" target="_blank">
<img style="border-radius: 20px" src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174">
</a>

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
usage: run.py [-h] [-d DIR] [-p PASSWORD] [-t THREAD] url

positional arguments:
  url

options:
  -h, --help   show this help message and exit
  -d DIR       output directory
  -p PASSWORD  password
  -t THREAD    number of threads (default: 1)
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

#### Example 3: Download files from https://gofile.io/d/foobar with password "1234" protected ####
```console
python run.py -p 1234 https://gofile.io/d/foobar
```

#### Example 3: Download files from https://gofile.io/d/foobar with 4 threads ####
```console
python run.py -t 4 https://gofile.io/d/foobar
```

## License ##
This project is licensed under the [MIT License](LICENSE.md)
