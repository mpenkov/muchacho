import json
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


def _relpath(c, videopath):
    return os.path.relpath(videopath, start=c._subdir)


@cherrypy.expose
class Api:
    def __init__(self, cache_):
        self.cache = cache_

    @cherrypy.tools.json_out()
    def GET(self, videoid=None, action=None, formatstr=None):
        if videoid is None:
            self.cache.reload()
            return [
                {
                    "id": i,
                    "relpath": _relpath(self.cache, self.cache[i].path),
                } for i in self.cache
            ]

        video = self.cache[videoid]

        if action is None:
            return {
                'id': videoid,
                "relpath": _relpath(self.cache, video.path),
                'meta': video.load_meta(),
            }

        elif action == 'preview_relpath':
            if formatstr[0] == '/':
                formatstr = os.path.join(cache._subdir, formatstr)
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

        raise NotImplementedError

    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def PUT(self, videoid):
        video = self.cache[videoid]
        relpath = cherrypy.request.json['relpath']
        self.cache.rename(video, relpath)
        return {
            'id': videoid,
            'relpath': relpath,
        }

    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def POST(self):
        url = cherrypy.request.json['url']
        json_bytes = subprocess.check_output(['youtube-dl', '--dump-json', url])
        info = json.loads(json_bytes)
        self.cache.async_add(info["id"])
        return info


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--subdir', default=os.path.join(os.path.dirname(__file__), 'gitignore'))
    args = parser.parse_args()

    monitor = multiprocessing.Process(target=cache.monitor, args=(args.subdir, ))
    monitor.daemon = True
    monitor.start()

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
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': os.path.join(root, 'static'),
        },
    }
    cache_ = cache.Cache(args.subdir)
    server = Server(cache_)
    server.videos = Api(cache_)
    cherrypy.quickstart(server, '/', conf)


if __name__ == '__main__':
    main()
