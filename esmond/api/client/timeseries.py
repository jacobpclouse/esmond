import json
import requests
import warnings

from esmond.api.api import QueryUtil
from esmond.api.client.snmp import DataPayload

class TimeseriesBase(object):
    """Base class for the GET and POST timeseries interaction objects."""
    _schema_root = 'v1/timeseries'
    def __init__(self, api_url='http://localhost/', path=[], freq=None):
        """Constructor - the path list arg is an ordered list of elements
        that will be used (along with the freq arg) to construct the 
        cassandra row key.  See example above."""
        super(TimeseriesBase, self).__init__()
        self.api_url = api_url
        self.path = path[:] # copy in case the path ref is reused
        self.freq = freq

        # Make sure we're not using the base class
        try:
            getattr(self, '_p_type')
        except AttributeError:
            raise PostException('Do not instantiate TimeseriesBase base class, use appropriate subclass.')

        # Validate args
        if not self.path or not self.freq or not self.api_url:
            raise PostException('The args api_url, path and freq must be set.')

        if not isinstance(self.path, list):
            raise PostException('Path argument must be a list.')

        if not len(self.path) > 1:
            raise PostException('Path is not of sufficient length.')

        try:
            int(self.freq)
        except ValueError:
            raise PostException('Arg freq must be an integer.')

        self.path = QueryUtil.encode_datapath(self.path)

        self.url = '{0}{1}/{2}/{3}/{4}'.format(self.api_url, 
            self._schema_root, self._p_type,
            '/'.join(self.path), self.freq)

    def _issue_warning(self, message):
        """Use to issue a subclass-specific warning."""
        warnings.warn(message, self._wrn, stacklevel=2)

"""
Classes to handle posting data to esmond rest interface.

Example use:

    ts = int(time.time()) * 1000

    payload = [
        { 'ts': ts-90000, 'val': 1000 },
        { 'ts': ts-60000, 'val': 2000 },
        { 'ts': ts-30000, 'val': 3000 },
        { 'ts': ts, 'val': 4000 },
    ]

    path = ['rtr_test_post', 'FastPollHC', 'ifHCInOctets', 'interface_test']

    p = PostRawData(port=8000, path=path, freq=30000)
    p.set_payload(payload)
    p.add_to_payload({'ts': ts+1000, 'val': 5000})
    p.send_data()

The internal payload is initialized to an empty list.  The client can either
compltely overwrite the internal payload with the set_payload() method, or 
one can add indivdual dicts to it with add_to_payload().  

In either case, the payload will be internally validated and an exception
will be raised if bad data is found.
"""

class PostWarning(Warning): pass
class PostRawDataWarning(PostWarning): pass
class PostBaseRateWarning(PostWarning): pass

class PostException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class PostData(TimeseriesBase):
    """Base class for API write objects - writes data to the POST 
    facility in the /timeseries/ REST interface namespace."""
    _wrn = PostWarning

    def __init__(self, api_url='http://localhost/', path=[], freq=None):
        """Constructor - the path list arg is an ordered list of elements
        that will be used (along with the freq arg) to construct the 
        cassandra row key.  See example above."""
        super(PostData, self).__init__(api_url, path, freq)

        # Make sure we're not using an intermediate base class.
        try:
            getattr(self, '_p_type')
        except AttributeError:
            raise PostException('Do not instantiate PostData base class, use appropriate subclass.')

        # Set up playload and headers.

        self.payload = []
        self.headers = {'content-type': 'application/json'}

    def set_payload(self, payload):
        """Sets object payload to a complete list of dicts passed in. 
        This will overwrite the internal payload if any elements had 
        been previously defined (and issue a warning)."""
        if not isinstance(payload, list):
            raise PostException('Arg payload to set_payload must be a list instance.')

        if len(self.payload):
            self._issue_warning('Internal payload was not empty, so this is a warning that you are overwriting an existing payload.')

        self.payload = payload

        self._validate_payload()

    def add_to_payload(self, item):
        """Adds a new dict element to the object payload."""
        if not isinstance(item, dict):
            raise PostException('Arg item to add_to_payload must be a dict instance.')

        self.payload.append(item)

        self._validate_payload()

    def _validate_payload(self):
        """Internal method to check the integrity of the payload whenever 
        it is set or appended to."""
        for i in self.payload:
            if not isinstance(i, dict):
                raise PostException('All elements of payload must be dicts - got: {0}'.format(i))
            if not i.has_key('ts') or not i.has_key('val'):
                raise PostException('Expecting list of dicts with keys \'val\' and \'ts\' - got: {0}'.format(i))
            try:
                int(float(i.get('ts')))
                float(i.get('val'))
            except ValueError:
                raise PostException('Must supply valid numeric args for ts and val dict attributes - got: {0}'.format(i))

    def send_data(self):
        """Format current payload, send to REST api and clear the payload.
        Payload is cleared after a write so as not to send duplicate data, 
        and so the same instance can be used to send multiple times."""

        if not self.payload:
            self._issue_warning('Payload empty, no data sent.')
            return

        r = requests.post(self.url, data=json.dumps(self.payload), headers=self.headers)

        if not r.status_code == 201:
            # Change this to an exception?
            self._issue_warning('POST error: status_code: {0}, message: {1}'.format(r.status_code, r.content))

        # reset payload
        self.payload = []



class PostRawData(PostData):
    """Class to post raw data to rest api."""
    _p_type = 'RawData'
    _wrn = PostRawDataWarning

class PostBaseRate(PostData):
    """Class to post base rate deltas to rest api."""
    _p_type = 'BaseRate'
    _wrn = PostBaseRateWarning

"""
Classes to execute get requests to timeseries namespace.

These classes are initialized much like the post data class, but with 
and additional params dict arg that will be passed to the GET request.
Setting begin or end time would be the most common args set.  Params dict 
is optional.

Get data will return a payload encapsulation object which will return 
data point objects.  Since this namespace is supposed to just return 
that which is in the backend - the timestamps are all in milliseconds 
and there is no coersion to a python datetime object.

Example usage:

    path = ['rtr_test_post', 'FastPollHC', 'ifHCInOctets', 'interface_test/0/0.0']

    params = {
        'begin': ts-90000, 'end': ts+1000
    }

    get = None

    args = {
        'api_url': 'http://localhost:8000/', 
        'path': path, 
        'freq': 30000,
        'params': params,
    }

    if p_type == 'RawData':
        get = GetRawData(**args)
    elif p_type == 'BaseRate':
        get = GetBaseRate(**args)

    payload = get.get_data()

    print payload
    for d in payload.data:
        print '  *', d
"""

class GetWarning(Warning): pass
class GetRawDataWarning(GetWarning): pass
class GetBaseRateWarning(GetWarning): pass

class GetException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class GetData(TimeseriesBase):
    """Base class for API write objects - writes data to the Get 
    facility in the /timeseries/ REST interface namespace."""
    _wrn = GetWarning
    def __init__(self, api_url='http://localhost/', path=[], freq=None, params={}):
        """Constructor - the path list arg is an ordered list of elements
        that will be used (along with the freq arg) to construct the 
        cassandra row key.  See example above."""
        super(GetData, self).__init__(api_url, path, freq)

        self._params = params

        # Make sure we're not using an intermediate base class.
        try:
            getattr(self, '_p_type')
        except AttributeError:
            raise PostException('Do not instantiate GetData base class, use appropriate subclass.')

    def get_data(self):
        r = requests.get(self.url, params=self._params)
        if r.status_code == 200 and \
            r.headers['content-type'] == 'application/json':
            data = json.loads(r.content)
            return TimeSeriesDataPayload(data)
        else:
            self._issue_warning('GET error: status_code: {0}, message: {1}'.format(r.status_code, r.content))
            return TimeSeriesDataPayload()

class GetRawData(GetData):
    """Class to Get raw data to rest api."""
    _p_type = 'RawData'
    _wrn = GetRawDataWarning

class GetBaseRate(GetData):
    """Class to Get base rate deltas to rest api."""
    _p_type = 'BaseRate'
    _wrn = GetBaseRateWarning

"""Encapsulation objects for the returned data.  Subclasses the sibling
classes in the api.client.snmp module and overrides to get rid of the 
utc timestamp coersion since this is all in ms."""

class TimeSeriesDataPayload(DataPayload):
    def __init__(self, data={'data':[]}):
        super(TimeSeriesDataPayload, self).__init__(data)

    @property
    def begin_time(self):
        return self._data.get('begin_time', None)

    @property
    def end_time(self):
        return self._data.get('end_time', None)

    @property
    def data(self):
        """Return internal data from payload as list of DataPoint."""
        return [TimeSeriesDataPoint(x[0],x[1]) for x in self._data.get('data', [])]

class TimeSeriesDataPoint(object):
    """Class to encapsulate the returned data points."""
    def __init__(self, ts, val):
        super(TimeSeriesDataPoint, self).__init__()
        self.ts = ts
        self.val = val

    def __repr__(self):
        return '<DataPoint: ts:{0} val:{1}>'.format(self.ts, self.val)
