import json
import logging
import os
import re
import subprocess
import tempfile
import time
import urllib.request

_TO_ADD = '.to-add'
_INFO_SUFFIX = '.info.json'
_THUMB_SUFFIX = '-thumb.jpg'
_THUMB_EXT = ('.jpg', '.webp')
_VIDEO_EXT = ('.mp4', '.avi', '.mkv', '.webm')


def monitor(subdir, terminate_event, sleep_seconds=30):
    cache = Cache(subdir)
    to_add_subdir = os.path.join(subdir, _TO_ADD)
    os.makedirs(to_add_subdir, exist_ok=True)

    while not terminate_event.is_set():
        for f in os.listdir(to_add_subdir):
            if f.endswith('.json'):
                path = os.path.join(to_add_subdir, f)
                with open(path) as fin:
                    info = json.load(fin)

                logging.info('adding %r', info)
                cache.add(videoid=info['id'], subdir=info.get('subdir'))
                os.unlink(path)
        logging.info('sleeping for %ds', sleep_seconds)
        time.sleep(sleep_seconds)

        cache.reload()


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

    def assert_meta(self):
        if not os.path.isfile(self.meta_path):
            match = re.search(r'\[([A-Za-z0-9_-]{11})\]', self.filename)
            assert match
            videoid = match.group(1)
            command = ['youtube-dl', '--dump-json', videoid]
            output = subprocess.check_output(command)
            with open(self.meta_path, 'wb') as fout:
                fout.write(output)

    def assert_thumbnail(self):
        if not os.path.isfile(self.thumb_path):
            meta = self.load_meta()
            url = meta['thumbnail']
            ext = os.path.splitext(url)[1]
            buf = urllib.request.urlopen(url).read()
            with tempfile.NamedTemporaryFile(suffix=ext) as tmp:
                tmp.write(buf)
                tmp.flush()
                _postprocess_thumbnail(tmp.name, self.thumb_path, unlink=False)

    @property
    def files(self):
        stem, _ = os.path.splitext(self._filename)
        return (self._filename, stem + _INFO_SUFFIX, stem + _THUMB_SUFFIX)

    @property
    def path(self):
        return os.path.join(self._subdir, self._filename)

    @property
    def meta_path(self):
        stem, _ = os.path.splitext(self._filename)
        return os.path.join(self._subdir, stem + _INFO_SUFFIX)

    @property
    def thumb_path(self):
        stem, _ = os.path.splitext(self._filename)
        return os.path.join(self._subdir, stem + _THUMB_SUFFIX)

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

    def delete(self):
        for p in (self.path, self.thumb_path, self.meta_path):
            os.unlink(p)

    def ffprobe(self):
        command = 'ffprobe -show_streams -print_format json'.split() + [self._path]
        json_bytes = subprocess.check_output(command)
        return json.loads(json_bytes)


class Cache:
    def __init__(self, subdir):
        self._subdir = subdir
        self.reload()

    def reload(self):
        self._videos = {}

        for root, directories, files in os.walk(self._subdir):
            if root == _TO_ADD:
                continue
            for f in files:
                stem, ext = os.path.splitext(f)
                if ext.lower() in _VIDEO_EXT:
                    video = Video(os.path.join(root, f))
                    try:
                        meta = video.load_meta()
                    except FileNotFoundError:
                        continue
                    self._videos[meta['id']] = video

    def __contains__(self, videoid):
        return videoid in self._videos

    def __getitem__(self, item):
        return self._videos[item]

    def __iter__(self):
        return iter(self._videos)

    def items(self):
        return self._videos.items()

    def async_add(self, videoid, subdir=None):
        path = os.path.join(self._subdir, _TO_ADD)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, videoid) + '.json', 'w') as fout:
            json.dump({'id': videoid, 'subdir': subdir}, fout)

    def add(self, videoid, subdir=None):
        try:
            video = self._videos[videoid]
        except KeyError:
            rename_to = None
        else:
            rename_to = os.path.relpath(video.path, start=self._subdir)
            video.delete()
            del self._videos[videoid]

        command = [
            'youtube-dl',
            '--format', 'bestvideo+bestaudio/best',
            '--print-json',
            '--write-info-json',
            '--write-thumbnail',
            '--id',
            '--',
            videoid,
        ]
        if subdir is None:
            subdir = os.path.join(self._subdir, 'unsorted')
            os.makedirs(subdir, exist_ok=True)
        else:
            subdir = os.path.join(self._subdir, subdir.strip('/'))

        json_bytes = subprocess.check_output(command, cwd=subdir)
        json_str = json_bytes.decode('utf-8')
        info = json.loads(json_str)
        info.pop('formats', None)
        info.pop('requested_formats', None)
        print(json.dumps(info, indent=2, sort_keys=True))

        for ext in _THUMB_EXT:
            thumb_name = info['id'] + ext
            thumb_path = os.path.join(subdir, thumb_name)
            if os.path.isfile(thumb_path):
                _postprocess_thumbnail(thumb_path)
                break
        else:
            assert False, 'could not find thumbnail for video %(id)r' % info

        if rename_to:
            #
            # NB. We could also reload the cache at this point, but that
            # would be slower.
            #
            for f in os.listdir(subdir):
                stem, ext = os.path.splitext(f)
                if ext in _VIDEO_EXT:
                    video = Video(os.path.join(subdir, f))
                    break
            else:
                assert False, 'could not find video for video %(id)r' % info

            self.rename(video, rename_to)

    def rename(self, video, relpath):
        abspath = os.path.join(self._subdir, relpath)
        if video.path == abspath:
            # Nothing to do
            return

        if os.path.isdir(abspath):
            abspath = os.path.join(abspath, video.filename)

        abs_stem, ext = os.path.splitext(abspath)

        destination_files = (
            abspath,
            abs_stem + _INFO_SUFFIX,
            abs_stem + _THUMB_SUFFIX,
        )
        for f in destination_files:
            assert not os.path.isfile(f), 'destination %r already exists' % f

        source_files = [
            os.path.join(video._subdir, f)
            for f in video.files
        ]
        for f in source_files:
            assert os.path.isfile(f), 'source %r does not exist' % f

        os.makedirs(os.path.dirname(abspath), exist_ok=True)
        for src, dst in zip(source_files, destination_files):
            print('mv %r %r' % (src, dst))
            os.rename(src, dst)

        video.reload(abspath)
        self._videos[video.load_meta()['id']] = video

        return os.path.relpath(abspath, start=self._subdir)

    def relpath(self, videoid):
        return os.path.relpath(self._videos[videoid].path, start=self._subdir)


def _postprocess_thumbnail(input_path, output_path=None, unlink=True):
    if output_path is None:
        stem, ext = os.path.splitext(input_path)
        output_path = stem + _THUMB_SUFFIX
    assert output_path
    assert output_path != input_path

    command = ['ffmpeg', '-y', '-i', input_path, '--', output_path]
    subprocess.check_call(command)

    if unlink:
        os.unlink(input_path)
