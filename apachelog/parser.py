import re


class ApacheLogParserError(Exception):
    pass


class AttrDict(dict):
    """
    Allows dicts to be accessed via dot notation as well as subscripts
    Makes using the friendly names nicer
    """
    def __getattr__(self, name):
        return self[name]

"""
Frequenty used log formats stored here
"""
FORMATS = {
    # Common Log Format (CLF)
    'common':r'%h %l %u %t \"%r\" %>s %b',

    # Common Log Format with Virtual Host
    'vhcommon':r'%v %h %l %u %t \"%r\" %>s %b',

    # NCSA extended/combined log format
    # (common + "%{Referer}i" + "%{User-Agent}i")
    'extended':r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"',

    # Nginx default log format (extended + "$gzip_ratio")
    'nginx':r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\" \"%{gzip-ratio}i\"',
    }


class Parser (object):
    format_to_name = {
        # Explanatory comments copied from
        # http://httpd.apache.org/docs/2.2/mod/mod_log_config.html
        # Remote IP-address
        '%a':'remote_ip',
        # Local IP-address
        '%A':'local_ip',
        # Size of response in bytes, excluding HTTP headers.
        '%B':'response_bytes',
        # Size of response in bytes, excluding HTTP headers. In CLF
        # format, i.e. a "-" rather than a 0 when no bytes are sent.
        '%b':'response_bytes_clf',
        # The contents of cookie Foobar in the request sent to the server.
        # Only version 0 cookies are fully supported.
        #'%{Foobar}C':'',
        '%{}C':'cookie',
        # The time taken to serve the request, in microseconds.
        '%D':'response_time_us',
        # The contents of the environment variable FOOBAR
        #'%{FOOBAR}e':'',
        '%{}e':'env',
        # Filename
        '%f':'filename',
        # Remote host
        '%h':'remote_host',
        # The request protocol
        '%H':'request_protocol',
        # The contents of Foobar: header line(s) in the request sent to
        # the server. Changes made by other modules (e.g. mod_headers)
        # affect this.
        #'%{Foobar}i':'',
        '%{}i':'header',
        # Number of keepalive requests handled on this connection.
        # Interesting if KeepAlive is being used, so that, for example,
        # a "1" means the first keepalive request after the initial one,
        # "2" the second, etc...; otherwise this is always 0 (indicating
        # the initial request). Available in versions 2.2.11 and later.
        '%k':'keepalive_num',
        # Remote logname (from identd, if supplied). This will return a
        # dash unless mod_ident is present and IdentityCheck is set On.
        '%l':'remote_logname',
        # The request method
        '%m':'request_method',
        # The contents of note Foobar from another module.
        #'%{Foobar}n':'',
        '%{}n':'note',
        # The contents of Foobar: header line(s) in the reply.
        #'%{Foobar}o':'',
        '%{}o':'reply_header',
        # The canonical port of the server serving the request
        '%p':'server_port',
        # The canonical port of the server serving the request or the
        # server's actual port or the client's actual port. Valid
        # formats are canonical, local, or remote.
        #'%{format}p':"",
        '%{}p':'port',
        # The process ID of the child that serviced the request.
        '%P':'process_id',
        # The process ID or thread id of the child that serviced the
        # request. Valid formats are pid, tid, and hextid. hextid requires
        # APR 1.2.0 or higher.
        #'%{format}P':'',
        '%{}P':'pid',
        # The query string (prepended with a ? if a query string exists,
        # otherwise an empty string)
        '%q':'query_string',
        # First line of request
        # e.g., what you'd see in the logs as 'GET / HTTP/1.1'
        '%r':'first_line',
        # The handler generating the response (if any).
        '%R':'response_handler',
        # Status. For requests that got internally redirected, this is
        # the status of the *original* request --- %>s for the last.
        '%s':'status',
        '%>s':'last_status',
        # Time the request was received (standard english format)
        '%t':'time',
        # The time, in the form given by format, which should be in
        # strftime(3) format. (potentially localized)
        #'%{format}t':'TODO',
        # The time taken to serve the request, in seconds.
        '%T':'response_time_sec',
        # Remote user (from auth; may be bogus if return status (%s) is 401)
        '%u':'remote_user',
        # The URL path requested, not including any query string.
        '%U':'url_path',
        # The canonical ServerName of the server serving the request.
        '%v':'canonical_server_name',
        # The server name according to the UseCanonicalName setting.
        '%V':'server_name_config', #TODO: Needs better name
        # Connection status when response is completed:
        # X = connection aborted before the response completed.
        # + = connection may be kept alive after the response is sent.
        # - = connection will be closed after the response is sent.
        '%X':'completed_connection_status',
        # Bytes received, including request and headers, cannot be zero.
        # You need to enable mod_logio to use this.
        '%I':'bytes_received',
        # Bytes sent, including headers, cannot be zero. You need to
        # enable mod_logio to use this
        '%O':'bytes_sent',
    }

    def __init__(self, format, use_friendly_names=False):
        """
        Takes the log format from an Apache configuration file.

        Best just copy and paste directly from the .conf file
        and pass using a Python raw string e.g.

        format = r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"'
        p = apachelog.parser(format)
        """
        self._names = []
        self._regex = None
        self._pattern = ''
        self._use_friendly_names = use_friendly_names
        self._parse_format(format)

    def _parse_format(self, format):
        """
        Converts the input format to a regular
        expression, as well as extracting fields

        Raises an exception if it couldn't compile
        the generated regex.
        """
        format = format.strip()
        format = re.sub('[ \t]+',' ',format)

        subpatterns = []

        findquotes = re.compile(r'^\\"')
        findreferreragent = re.compile('Referer|User-Agent', re.I)
        findpercent = re.compile('^%.*t$')
        lstripquotes = re.compile(r'^\\"')
        rstripquotes = re.compile(r'\\"$')
        self._names = []

        for element in format.split(' '):

            hasquotes = 0
            if findquotes.search(element): hasquotes = 1

            if hasquotes:
                element = lstripquotes.sub('', element)
                element = rstripquotes.sub('', element)

            if self._use_friendly_names:
                self._names.append(self.alias(element))
            else:
                self._names.append(element)

            subpattern = '(\S*)'

            if hasquotes:
                if element == '%r' or findreferreragent.search(element):
                    subpattern = r'\"([^"\\]*(?:\\.[^"\\]*)*)\"'
                else:
                    subpattern = r'\"([^\"]*)\"'

            elif findpercent.search(element):
                subpattern = r'(\[[^\]]+\])'

            elif element == '%U':
                subpattern = '(.+?)'

            subpatterns.append(subpattern)

        self._pattern = '^' + ' '.join(subpatterns) + '$'
        try:
            self._regex = re.compile(self._pattern)
        except Exception, e:
            raise ApacheLogParserError(e)

    def parse(self, line):
        """
        Parses a single line from the log file and returns
        a dictionary of it's contents.

        Raises and exception if it couldn't parse the line
        """
        line = line.strip()
        match = self._regex.match(line)

        if match:
            data = AttrDict()
            for k, v in zip(self._names, match.groups()):
                data[k] = v
            return data

        raise ApacheLogParserError("Unable to parse: %s with the %s regular expression" % ( line, self._pattern ) )

    def alias(self, name):
        """
        Override / replace this method if you want to map format
        field names to something else. This method is called
        when the parser is constructed, not when actually parsing
        a log file

        For custom format names, such as %{Foobar}C, 'Foobar' is referred to
        (in this function) as the custom_format and '%{}C' as the name

        If the custom_format has a '-' in it (and is not a time format), then the
        '-' is replaced with a '_' so the name remains a valid identifier.

        Takes and returns a string fieldname
        """

        custom_format = ''

        if name.startswith('%{'):
            custom_format = '_' + name[2:-2]
            name = '%{}' + name[-1]

            if name != '%{}t':
                custom_format = custom_format.replace('-', '_')

        try:
            return self.format_to_name[name] + custom_format
        except KeyError:
            return name

    def pattern(self):
        """
        Returns the compound regular expression the parser extracted
        from the input format (a string)
        """
        return self._pattern

    def names(self):
        """
        Returns the field names the parser extracted from the
        input format (a list)
        """
        return self._names
