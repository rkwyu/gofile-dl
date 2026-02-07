# Gofile-dl [![python](https://img.shields.io/badge/Python-3.11-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)  ![Regression Tests](https://github.com/rkwyu/gofile-dl/actions/workflows/test.yml/badge.svg)  

<a href="https://buymeacoffee.com/r1y5i" target="_blank">
<img style="border-radius: 20px" src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174">
</a>

## About ##
A command-line tool for downloading files from [gofile.io](https://gofile.io/) where you are authorized to access them.

## ⚠️ Legal & Ethical Notice ##

Use this tool __only on files that you have permission to download__, such as:
- Files you uploaded yourself
- Publicly shared files
- Files you have been explicitly granted access to

Unauthorized downloading or redistribution of copyrighted material may violate copyright law.
The authors of this project are __not responsible for misuse__.

## About ##

gofile-dl is a utility that helps you download files from Gofile.io efficiently. It supports batch downloads and can save files to a specified local directory.

> This tool does not bypass protections or provide access to private content without authorization.

## Prerequisites ##

- Python 3.10+ (recommended: latest stable release)
- pip installed

Confirm installation:
```console
python --version
pip --version
```

## Setup ##

Clone the repository and install dependencies:
```console
git clone https://github.com/rkwyu/gofile-dl
cd gofile-dl
pip install -r requirements.txt
```

## Usage (CLI) ##
```console
usage: run.py [-h] [-f FILE] [-t NUM_THREADS] [-d DIR] [-p PASSWORD] [-x PROXY] [-i INCLUDES] [-e EXCLUDES] [url]

positional arguments:
  url             url to process (if not using -f)

options:
  -h, --help      show this help message and exit
  -f FILE         local file to process
  -t NUM_THREADS  number of threads (default: 1)
  -d DIR          output directory
  -p PASSWORD     password
  -x PROXY        proxy server (format: ip/host:port)
  -i INCLUDES     included files (supporting wildcard *)
  -e EXCLUDES     excluded files (supporting wildcard *)
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

#### Example 4: Download files from https://gofile.io/d/foobar with 4 threads ####
```console
python run.py -t 4 https://gofile.io/d/foobar
```

#### Example 5: Download files from https://gofile.io/d/foobar except *.jpg, foo.bar files ####
```console
python run.py -e "*.jpg" -e "foo.bar" https://gofile.io/d/foobar
```

#### Example 6: Download files from https://gofile.io/d/foobar including only *.png, except xyz.png files ####
```console
python run.py -i "*.png" -e "xyz.png" https://gofile.io/d/foobar
```

#### Example 7: Download files from a local file ####
```console
echo "https://gofile.io/d/foobar" > input.txt
python run.py -f ./input.txt
```

## Why This Matters ##

This README clarifies that gofile-dl is intended for use only on authorized content. It is the user’s responsibility to comply with copyright law and the platform’s terms of service.

## Disclaimer ##

This project is not affiliated with or endorsed by Gofile.io.

All trademarks and copyrights belong to their respective owners.

## License ##
This project is licensed under the [MIT License](LICENSE.md)
