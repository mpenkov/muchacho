import json
import logging
import os
import multiprocessing
import subprocess

import cherrypy

import cache


class Server:
    def __init__(self, cache_):
        self.cache = cache_

    @cherrypy.expose
    def index(self):
        with open("static/index.html") as fin:
            return fin.read()

    @cherrypy.expose
    def player(self, videoid):
        src = "/cache/" + self.cache.relpath(videoid)
        with open("static/player.html") as fin:
            return fin.read().replace("{{ src }}", src)


def _relpath(c, videopath):
    return os.path.relpath(videopath, start=c._subdir)


@cherrypy.expose
class VideoApi:
    def __init__(self, cache_):
        self.cache = cache_

    @cherrypy.tools.json_out()
    def GET(self, videoid=None, action=None, formatstr=None, subdir=''):
        if videoid is None:
            self.cache.reload()
            subdir = subdir.strip('/')
            videos = [
                {
                    "id": i,
                    "filename": self.cache[i].filename,
                    "subdir": self.cache[i].subdir,
                    "relpath": _relpath(self.cache, self.cache[i].path),
                }
                for i in self.cache
                if _relpath(self.cache, self.cache[i].path).startswith(subdir)
            ]
            for v in videos:
                meta = self.cache[v['id']].load_meta()
                v['meta'] = {
                    'title': meta['title'],
                    'thumbnail': meta['thumbnail'],
                }
            return sorted(videos, key=lambda v: v['filename'])

        video = self.cache[videoid]

        if action is None:
            return {
                'id': videoid,
                'filename': video.filename,
                'subdir': video.subdir,
                'relpath': _relpath(self.cache, video.path),
                'meta': video.load_meta(),
            }

        elif action == 'preview_relpath':
            if formatstr[0] == '/':
                formatstr = os.path.join(self.cache._subdir, formatstr[1:])
            else:
                formatstr = os.path.join(video.subdir, formatstr)

            try:
                path = formatstr % video.load_meta()
            except ValueError:
                # TODO: do something with the error in the UI?
                path = video.path

            return {
                'id': videoid,
                'relpath': _relpath(self.cache, path)
            }

        if action == 'ffprobe':
            return video.ffprobe()

        raise NotImplementedError

    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def PUT(self, videoid):
        video = self.cache[videoid]
        relpath = cherrypy.request.json['relpath']
        relpath = self.cache.rename(video, relpath)
        return {
            'id': videoid,
            'relpath': relpath,
        }

    def DELETE(self, videoid):
        video = self.cache[videoid]
        video.delete()
        return None

    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def POST(self):
        url = cherrypy.request.json['url']
        logging.critical('POST url: %r', url)
        json_bytes = subprocess.check_output(['youtube-dl', '--dump-json', url])
        info = json.loads(json_bytes)
        self.cache.async_add(info["id"])
        return info


@cherrypy.expose
class SubdirsApi:
    def __init__(self, cache_):
        self.cache = cache_

    @cherrypy.tools.json_out()
    def GET(self):
        return [
            {
                'name': s,
                'folder_jpg': None,
            }
            for s in sorted(os.listdir(self.cache._subdir))
            if os.path.isdir(os.path.join(self.cache._subdir, s))
            and not s.startswith('.')
        ]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--subdir', default=os.path.join(os.path.dirname(__file__), 'gitignore'))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    terminate_event = multiprocessing.Event()
    monitor = multiprocessing.Process(
        target=cache.monitor,
        args=(args.subdir, terminate_event),
    )

    def start():
        logging.critical('starting monitor subprocess')
        monitor.start()

    def stop():
        logging.critical('stopping monitor subprocess')
        terminate_event.set()
        monitor.join()
        logging.critical('stopped monitor subprocess')

    #
    # https://stackoverflow.com/questions/11078254/how-to-detect-if-cherrypy-is-shutting-down
    #
    cherrypy.engine.subscribe('start', start)
    cherrypy.engine.subscribe('stop', stop)

    root = os.path.abspath(os.path.dirname(__file__))
    conf = {
        'global': {
            'server.socket_port': 8088,
        },
        '/': {
            'tools.staticdir.root': root,
        },
        '/videos': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        },
        '/subdirs': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': os.path.join(root, 'static'),
        },
        '/cache': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': args.subdir,
        },
    }
    cache_ = cache.Cache(args.subdir)
    server = Server(cache_)
    server.videos = VideoApi(cache_)
    server.subdirs = SubdirsApi(cache_)
    cherrypy.quickstart(server, '/', conf)


if __name__ == '__main__':
    main()
