import json
import os
import multiprocessing
import subprocess

import cherrypy

import cache


class Server:
    def __init__(self, subdir):
        self.cache = cache.Cache(subdir)

    @cherrypy.expose
    def index(self):
        with open("index.html") as fin:
            return fin.read()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def add(self):
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

    conf = {
        'global': {
            'server.socket_port': 8088,
        }
    }
    cherrypy.quickstart(Server(args.subdir), '/', conf)


if __name__ == '__main__':
    main()
