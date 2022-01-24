# YOLOv5 🚀 by Ultralytics, GPL-3.0 license
"""
Download utils
"""

from nis import cat
import os
import platform
import re
import requests
import subprocess
import time
import urllib
from pathlib import Path
from zipfile import ZipFile

from kili.client import Kili
import requests
import torch
from tqdm import tqdm


def gsutil_getsize(url=''):
    # gs://bucket/file size https://cloud.google.com/storage/docs/gsutil/commands/du
    s = subprocess.check_output(f'gsutil du {url}', shell=True).decode('utf-8')
    return eval(s.split(' ')[0]) if len(s) else 0  # bytes


def safe_download(file, url, url2=None, min_bytes=1E0, error_msg=''):
    # Attempts to download file from url or url2, checks and removes incomplete downloads < min_bytes
    file = Path(file)
    assert_msg = f"Downloaded file '{file}' does not exist or size is < min_bytes={min_bytes}"
    try:  # url1
        print(f'Downloading {url} to {file}...')
        torch.hub.download_url_to_file(url, str(file))
        assert file.exists() and file.stat().st_size > min_bytes, assert_msg  # check
    except Exception as e:  # url2
        file.unlink(missing_ok=True)  # remove partial downloads
        print(f'ERROR: {e}\nRe-attempting {url2 or url} to {file}...')
        os.system(f"curl -L '{url2 or url}' -o '{file}' --retry 3 -C -")  # curl download, retry and resume on fail
    finally:
        if not file.exists() or file.stat().st_size < min_bytes:  # check
            file.unlink(missing_ok=True)  # remove partial downloads
            print(f"ERROR: {assert_msg}\n{error_msg}")
        print('')


def attempt_download(file, repo='ultralytics/yolov5'):  # from utils.downloads import *; attempt_download()
    # Attempt file download if does not exist
    file = Path(str(file).strip().replace("'", ''))

    if not file.exists():
        # URL specified
        name = Path(urllib.parse.unquote(str(file))).name  # decode '%2F' to '/' etc.
        if str(file).startswith(('http:/', 'https:/')):  # download
            url = str(file).replace(':/', '://')  # Pathlib turns :// -> :/
            file = name.split('?')[0]  # parse authentication https://url.com/file.txt?auth...
            if Path(file).is_file():
                print(f'Found {url} locally at {file}')  # file already exists
            else:
                safe_download(file=file, url=url, min_bytes=1E5)
            return file

        # GitHub assets
        file.parent.mkdir(parents=True, exist_ok=True)  # make parent dir (if required)
        try:
            response = requests.get(f'https://api.github.com/repos/{repo}/releases/latest').json()  # github api
            assets = [x['name'] for x in response['assets']]  # release assets, i.e. ['yolov5s.pt', 'yolov5m.pt', ...]
            tag = response['tag_name']  # i.e. 'v1.0'
        except Exception:  # fallback plan
            assets = ['yolov5n.pt', 'yolov5s.pt', 'yolov5m.pt', 'yolov5l.pt', 'yolov5x.pt',
                      'yolov5n6.pt', 'yolov5s6.pt', 'yolov5m6.pt', 'yolov5l6.pt', 'yolov5x6.pt']
            try:
                tag = subprocess.check_output('git tag', shell=True, stderr=subprocess.STDOUT).decode().split()[-1]
            except Exception:
                tag = 'v6.0'  # current release

        if name in assets:
            safe_download(file,
                          url=f'https://github.com/{repo}/releases/download/{tag}/{name}',
                          # url2=f'https://storage.googleapis.com/{repo}/ckpt/{name}',  # backup url (optional)
                          min_bytes=1E5,
                          error_msg=f'{file} missing, try downloading from https://github.com/{repo}/releases/')

    return str(file)


def gdrive_download(id='16TiPfZj7htmTyhntwcZyEEAejOUxuT6m', file='tmp.zip'):
    # Downloads a file from Google Drive. from yolov5.utils.downloads import *; gdrive_download()
    t = time.time()
    file = Path(file)
    cookie = Path('cookie')  # gdrive cookie
    print(f'Downloading https://drive.google.com/uc?export=download&id={id} as {file}... ', end='')
    file.unlink(missing_ok=True)  # remove existing file
    cookie.unlink(missing_ok=True)  # remove existing cookie

    # Attempt file download
    out = "NUL" if platform.system() == "Windows" else "/dev/null"
    os.system(f'curl -c ./cookie -s -L "drive.google.com/uc?export=download&id={id}" > {out}')
    if os.path.exists('cookie'):  # large file
        s = f'curl -Lb ./cookie "drive.google.com/uc?export=download&confirm={get_token()}&id={id}" -o {file}'
    else:  # small file
        s = f'curl -s -L -o {file} "drive.google.com/uc?export=download&id={id}"'
    r = os.system(s)  # execute, capture return
    cookie.unlink(missing_ok=True)  # remove existing cookie

    # Error check
    if r != 0:
        file.unlink(missing_ok=True)  # remove partial
        print('Download error ')  # raise Exception('Download error')
        return r

    # Unzip if archive
    if file.suffix == '.zip':
        print('unzipping... ', end='')
        ZipFile(file).extractall(path=file.parent)  # unzip
        file.unlink()  # remove zip

    print(f'Done ({time.time() - t:.1f}s)')
    return r


def get_token(cookie="./cookie"):
    with open(cookie) as f:
        for line in f:
            if "download" in line:
                return line.split()[-1]
    return ""

# Google utils: https://cloud.google.com/storage/docs/reference/libraries ----------------------------------------------
#
#
# def upload_blob(bucket_name, source_file_name, destination_blob_name):
#     # Uploads a file to a bucket
#     # https://cloud.google.com/storage/docs/uploading-objects#storage-upload-object-python
#
#     storage_client = storage.Client()
#     bucket = storage_client.get_bucket(bucket_name)
#     blob = bucket.blob(destination_blob_name)
#
#     blob.upload_from_filename(source_file_name)
#
#     print('File {} uploaded to {}.'.format(
#         source_file_name,
#         destination_blob_name))
#
#
# def download_blob(bucket_name, source_blob_name, destination_file_name):
#     # Uploads a blob from a bucket
#     storage_client = storage.Client()
#     bucket = storage_client.get_bucket(bucket_name)
#     blob = bucket.blob(source_blob_name)
#
#     blob.download_to_filename(destination_file_name)
#
#     print('Blob {} downloaded to {}.'.format(
#         source_blob_name,
#         destination_file_name))



def download_kili(data, kili_api_key):
    path = data.get('path', '')
    if '/kili/' not in path:
        return
    project_id = path.split('/')[-1]
    kili = Kili(api_key=kili_api_key)
    total = kili.count_assets(project_id=project_id)
    first = 100
    assets = []
    for skip in tqdm(range(0, total, first)):
        assets += kili.assets(
            project_id=project_id, 
            first=first, 
            skip=skip, 
            disable_tqdm=True,
            fields=[
                'id', 
                'content', 
                'labels.createdAt', 
                'labels.jsonResponse', 
                'labels.labelType'])
    assets = [{
            **a,
            'labels': [
                l for l in sorted(a['labels'], key=lambda l: l['createdAt']) \
                    if l['labelType'] in ['DEFAULT', 'REVIEW']
            ][-1:],
        } for a in assets]
    assets = [a for a in assets if len(a['labels']) > 0]
    train = data.get('train', '')
    os.makedirs(os.path.join(path, train), exist_ok=True)
    for asset in assets:
        img_data = requests.get(asset['content'], headers={
                'Authorization': f'X-API-Key: {kili_api_key}',
            }).content
        with open(os.path.join(path, train, asset['id'] + '.jpg'), 'wb') as handler:
            handler.write(img_data)
    names = data.get('names', [])
    path_labels = os.path.join(path, re.sub('^images', 'labels', train))
    os.makedirs(path_labels, exist_ok=True)
    for asset in assets:
        with open(os.path.join(path_labels, asset['id'] + '.txt'), 'w') as handler:
            json_response = asset['labels'][0]['jsonResponse']
            for job in json_response.values():
                for annotation in job.get('annotations', []):
                    name = annotation['categories'][0]['name']
                    category = names.index(name)
                    bounding_poly = annotation.get('boundingPoly', [])
                    if len(bounding_poly) < 1:
                        continue
                    if 'normalizedVertices' not in bounding_poly[0]:
                        continue
                    normalized_vertices = bounding_poly[0]['normalizedVertices']
                    x_s = [vertice['x'] for vertice in normalized_vertices]
                    y_s = [vertice['y'] for vertice in normalized_vertices]
                    x_min, y_min = min(x_s), min(y_s)
                    x_max, y_max = max(x_s), max(y_s)
                    _x_, _y_ = (x_max + x_min) / 2, (y_max + y_min) / 2
                    _w_, _h_ = x_max - x_min, y_max - y_min
                    handler.write(f'{category} {_x_} {_y_} {_w_} {_h_}\n')


        
