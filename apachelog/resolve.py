import os.path as _os_path
import pickle as _pickle
import re as _re
import socket as _socket


class Resolver (object):
    """A simple reverse-DNS resolver.

    Maintains a class-level cache of resolved IPs to avoid repeated
    lookups on the same IP address.

    Avoid hanging if we can't resolve a name.

    >>> import socket
    >>> if hasattr(_socket, 'setdefaulttimeout'):
    ...     socket.setdefaulttimeout(5)  # set 5 second timeout

    >>> r = Resolver()
    >>> r.IP = {}  # clear cache of date from previous tests
    >>> r.resolve('198.41.0.4')
    'a.root-servers.net'
    >>> r.IP
    {'198.41.0.4': ('a.root-servers.net', [], ['198.41.0.4'])}

    If you want to give shorter names to various DNS names, you can
    add an entry to the class-level ``REGEXPS``.  The entry should use
    your name as the key, and a list of matching regexps as the value.
    You need to enable this enhanced resolution using the ``smart``
    argument.

    >>> r.resolve('66.249.68.33')
    'crawl-66-249-68-33.googlebot.com'
    >>> r = Resolver(smart=True)
    >>> r.resolve('66.249.68.34')
    'googlebot'
    """
    IP = {}

    REGEXPS = {
        'feedburner': [_re.compile('.*rate-limited-proxy-.*.google.com.*')],
        }
    for bot in [
        'baiduspider',
        'googlebot',
        'msnbot',  # a.k.a: bingbot
        'yandex',
        ]:
        REGEXPS[bot] = [_re.compile('.*{}.*'.format(bot))]

    _cache_file = _os_path.expanduser(
        _os_path.join('~', '.apachelog-resolver.cache'))
    _cache_loaded = False
    _cache_dirty = None

    def __init__(self, smart=False):
        self._smart = smart
        self.load_cache()

    @classmethod
    def load_cache(self):
        if not self._cache_loaded:
            self._cache_loaded = True
            try:
                with open(self._cache_file, 'rb') as f:
                    self.IP = _pickle.load(f)
                self._cache_dirty = False
            except IOError:
                pass
            if self.IP is None:
                self.IP = {}

    @classmethod
    def save_cache(self):
        self.load_cache()  # avoid clobbering unloaded content
        if self._cache_dirty:
            with open(self._cache_file, 'wb') as f:
                _pickle.dump(self.IP, f)

    def resolve(self, ip):
        if ip not in self.IP:
            self._cache_dirty = True
            try:
                self.IP[ip] = _socket.gethostbyaddr(ip)
            except _socket.herror as e:
                self.IP[ip] = (ip, [], [ip])
            except _socket.gaierror as e:
                self.IP[ip] = (ip, [], [ip])
            else:
                if self._smart:
                    self._smart_resolve(ip)
        return self.IP[ip][0]

    def _smart_resolve(self, ip):
        x = self.IP[ip]
        if self._smart:
            for name,regexps in self.REGEXPS.items():
                for regexp in regexps:
                    if regexp.match(self.IP[ip][0]):
                        self.IP[ip] = (name, x[1], x[2])

    def ips(self, name):
        "Return a set of IP addresses used by a smart-resolved name."
        ips = set()
        for ip,values in self.IP.items():
            if values[0] == name:
                for x in values[2]:
                    ips.add(x)
        return ips
