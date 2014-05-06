from spotify.commands.manager import CommandManager
from spotify.components.base import Component
from spotify.components.manager import ComponentManager
from spotify.objects.user import User

from pyemitter import Emitter
import logging


log = logging.getLogger(__name__)


class Spotify(Component, Emitter):
    def __init__(self, user_agent=None):
        super(Spotify, self).__init__()

        # Create new HTTP session
        self.create_session(user_agent)

        # Construct modules
        self.commands = CommandManager(self)
        self.components = ComponentManager(self)

        # Session data
        self.config = None

        self.user_info = None
        self.user = None

    # User
    @property
    def username(self):
        return self.user_info.get('user')

    @property
    def country(self):
        return self.user_info.get('country')

    @property
    def catalogue(self):
        return self.user_info.get('catalogue')

    # Authentication
    def login(self, username=None, password=None, callback=None):
        self.components.authentication.login(username, password)
        return self.on('login', callback)

    def login_facebook(self, uid, token, callback=None):
        self.components.authentication.login_facebook(uid, token)
        return self.on('login', callback)

    def on_authenticated(self, config):
        self.config = config
        self._resolve_ap()

    # Resolve AP
    def _resolve_ap(self):
        params = {
            'client': '24:0:0:%s' % self.config['version']
        }

        resolver = self.config['aps']['resolver']
        log.debug('ap resolver: %s', resolver)

        if resolver.get('site'):
            params['site'] = resolver['site']

        # Connect to the AP resolver endpoint in order to determine
        # the WebSocket server URL to connect to next
        self.session.get(
            'http://%s' % resolver['hostname'],
            params=params
        ).add_done_callback(self._connect)

    # Connection
    def _connect(self, future):
        res = future.result()

        if res.status_code != 200:
            self.emit('error', 'Resolve AP - error, code %s' % res.status_code)
            return

        log.debug(
            'ap resolver - success, code: %s, content-type: %s',
            res.status_code,
            res.headers['content-type']
        )

        data = res.json()

        url = 'wss://%s/' % data['ap_list'][0]
        log.debug('Selected AP at "%s"', url)

        self.components.connection.connect(url)

    def on_command(self, name, *args):
        if self.commands.process(name, *args):
            return

        if name == 'login_complete':
            return self.on_login_complete()

        return self.emit('error', 'Unhandled command with name "%s"' % name)

    def on_login_complete(self):
        self.send('sp/log', 41, 1, 1656, 951, 0, 0)
        self.send('sp/log', 41, 1, 1656, 951, 0, 0)

        self.send('sp/user_info')\
            .on('success', self.on_user_info)

    def on_user_info(self, message):
        self.user_info = message['result']
        self.user = User(self, self.username)

        self.emit('login')

    # Messaging
    def send(self, name, *args):
        return self.components.connection.send(name, *args)

    def build(self, name, *args):
        return self.components.connection.build(name, *args)

    def send_request(self, request):
        return self.components.connection.send_request(request)

    def send_message(self, message):
        self.components.connection.send_message(message)

    # Metadata
    def metadata(self, uris, callback=None):
        return self.components.metadata.get(uris, callback)

    def playlist(self, uri, start=0, count=100, callback=None):
        return self.components.metadata.playlist(uri, start, count, callback)

    def playlists(self, username, start=0, count=100, callback=None):
        return self.components.metadata.playlists(username, start, count, callback)

    # Search
    def search(self, query, query_type='all', start=0, count=50, callback=None):
        return self.components.search.search(query, query_type, start, count, callback)
