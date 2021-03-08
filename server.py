import json
import os
import subprocess
import sqlite3

import cherrypy

DB_STRING = os.path.join(os.path.dirname(__file__), 'muchacho.sqlite3')
OUTPUT_FORMAT = 'muchacho/%(id)s.%(ext)s'


def setup_database():
    with sqlite3.connect(DB_STRING) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS v(id, json, path)")


@cherrypy.expose
class Server:
    def GET(self):
        return 'hello'

    def POST(self):
        url = json.load(cherrypy.request.body)['url']
        assert url

        # TODO: do we need youtube-dl here just for the ID extraction?
        json_bytes = subprocess.check_output(['youtube-dl', '--dump-json', url])
        video_id = json.loads(json_bytes)['id']

        with sqlite3.connect(DB_STRING) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM v WHERE id = ?", (video_id, ))
            (result, ) = next(cursor)

            if result == 0:
                # TODO: perform the download in a separate process
                command = [
                    'ssh', 'oberon',
                    'py39.venv/bin/youtube-dl', url,
                    '--format', 'best',
                    '--output', OUTPUT_FORMAT.replace('(', '\\(').replace(')', '\\)'),
                    '--print-json',
                ]
                json_bytes = subprocess.check_output(command)
                json_str = json_bytes.decode('utf-8')
                info = json.loads(json_str)
                info.pop('formats', None)
                info.pop('requested_formats', None)
                print(json.dumps(info, indent=2, sort_keys=True))

                path = OUTPUT_FORMAT % info
                cursor.execute("INSERT INTO v VALUES (?, ?, ?)", (video_id, json_str, path))
                conn.commit()

            cursor.close()


def main():
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'text/plain')],
        },
        'global': {
            'server.socket_port': 8088,
        }
    }
    setup_database()
    cherrypy.quickstart(Server(), '/', conf)


if __name__ == '__main__':
    main()

