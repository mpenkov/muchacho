import json
import logging
import os
import subprocess
import tempfile
import time
import urllib.request

_TO_ADD = '.to-add'


def monitor(subdir, sleep_seconds=60):
    cache = Cache(subdir)
    os.makedirs(os.path.join(subdir, _TO_ADD), exist_ok=True)

    while True:
        for videoid in os.listdir(os.path.join(subdir, _TO_ADD)):
            logging.info('adding %s', videoid)
            cache.add(videoid)
            os.unlink(os.path.join(subdir, _TO_ADD, videoid))
        logging.info('sleeping for %ds', sleep_seconds)
        time.sleep(sleep_seconds)


class Video:
    """Keeps a video file together with metadata and a filename.

    The metadata and filename must be named similarly to the video file.
    """
    def __init__(self, path):
        self.reload(path)

    def reload(self, path):
        self._path = path
        subdir, filename = os.path.split(self._path)
        stem, ext = os.path.splitext(filename)
        self._subdir = subdir
        self._filename = filename
        self._meta_filename = stem + '.info.json'

        # youtube-dl suffix is .jpg, but kodi looks for -thumb.jpg
        candidates = (stem + '.jpg', stem + '-thumb.jpg', stem + '.webp')
        for c in candidates:
            if os.path.isfile(os.path.join(subdir, c)):
                self._thumb_filename = c
                break
        else:
            self._thumb_filename = None

    @property
    def files(self):
        return (self._filename, self._meta_filename, self._thumb_filename)

    @property
    def path(self):
        return os.path.join(self._subdir, self._filename)

    @property
    def meta_path(self):
        return os.path.join(self._subdir, self._meta_filename)

    @property
    def thumb_path(self):
        return os.path.join(self._subdir, self._thumb_filename)

    @property
    def subdir(self):
        return self._subdir

    @property
    def filename(self):
        return self._filename

    def load_meta(self):
        with open(self.meta_path) as fin:
            return json.load(fin)

    def __repr__(self):
        return 'Video(%r)' % os.path.join(self._subdir, self._filename)


class Cache:
    def __init__(self, subdir):
        self._subdir = subdir
        self._videos = {}

        for root, directories, files in os.walk(subdir):
            if root == _TO_ADD:
                continue
            for f in files:
                stem, ext = os.path.splitext(f)
                if ext.lower() in ('.mp4', '.avi', '.mkv'):
                    video = Video(os.path.join(root, f))
                    meta = video.load_meta()
                    self._videos[meta['id']] = video

    def __contains__(self, videoid):
        return videoid in self._videos

    def __getitem__(self, item):
        return self._videos[item]

    def __iter__(self):
        return iter(self._videos)

    def items(self):
        return self._videos.items()

    def async_add(self, videoid):
        path = os.path.join(self._subdir, _TO_ADD)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, videoid), 'wb'):
            pass

    def add(self, videoid):
        if videoid in self._videos:
            raise ValueError('cache already contains video with id %r' % videoid)

        command = [
            'youtube-dl', videoid,
            '--format', 'best',
            '--print-json',
            '--write-info-json',
            '--write-thumbnail',
        ]
        json_bytes = subprocess.check_output(command, cwd=self._subdir)
        json_str = json_bytes.decode('utf-8')
        info = json.loads(json_str)
        info.pop('formats', None)
        info.pop('requested_formats', None)
        print(json.dumps(info, indent=2, sort_keys=True))

    def rename(self, video, relpath):
        abspath = os.path.join(self._subdir, relpath)
        abs_stem, ext = os.path.splitext(abspath)

        destination_files = (
            abspath,
            abs_stem + '.info.json',
            abs_stem + '-thumb%s' % os.path.splitext(video.thumb_path)[1],
        )
        for f in destination_files:
            assert not os.path.isfile(f)

        source_files = [
            os.path.join(video._subdir, f) if f else None
            for f in video.files
        ]
        os.makedirs(os.path.dirname(abspath), exist_ok=True)

        for src, dst in zip(source_files, destination_files):
            if src:
                os.rename(src, dst)

        video.reload(abspath)
