from .filter import Filter
import logging
import time

from ..statistics import mean, percentile, stddev
from ..util import Periodic
from ..event import Event
from pprint import pformat

class Stats(Filter):
    """Filter that produces aggregate statistics.

    It will produce:

    - name.count: number of data points
    - name.rate: the data points per second
    - name.mean: mean of data points
    - name.min: minimum data point
    - name.median: median data point
    - name.upper95: 95th% data point
    - name.upper99: 99th% data point
    - name.max: maximum data point
    - name.stddev: standard deviation

    This is emitted as a single event, every period.

    Example::

        Stats(metrics={'rails.{controller}.{action}.duration': 'duration'})

    :param integer period: period to report stats, in seconds
    :param map metrics: field names => values. Any fields from the events can
        be formatting into the field names. Values can be an event field, or a wildcard '*', to indicate
        generating statistics from any numerical fields.
    """
    def __init__(self, period=5, metrics=None):
        super(Stats, self).__init__()
        # configuration
        self.metrics = metrics or {}

        # transient state
        self.timers = {}

        self.last = time.time()
        self.periodic = Periodic(period, self.flush)
    
    def process(self, event):
        for path, v in self.metrics.iteritems():
            if v == '*':
                # wildcard stats - anything that is numeric
                values = event.iteritems()
            else:
                # specific stat
                values = [(v, event.get(v))]

            for key, value in values:
                if isinstance(value, (int, float)):
                    self._process_value(event, path, key, value)

    def _process_value(self, event, path, v, value):
        try:
            k = event.format(path, [v], raise_missing=True)
            try:
                # optimise for common case
                self.timers[k].add(value)
            except KeyError:
                self.timers[k] = Timer()
                self.timers[k].add(value)
        except KeyError:
            # event didn't contain all the necessary format keys - ignore
            pass

    def start(self):
        super(Stats, self).start()
        self.periodic.start()

    def stop(self):
        self.periodic.kill()
        self.periodic.join()
        super(Stats, self).stop()

    def flush(self):
        count = 0
        now = time.time()
        # calculate period for precise rate calculation
        period = now - self.last
        for k, timer in self.timers.iteritems():
            stats = timer.stats(period)
            if stats:
                count += 1
                if self.output:
                    self.output.put(Event(tags=['stat'], metric=k, stats=stats))
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug('%s: %s' % (k, pformat(stats)))
            timer.reset()
        if count:
            self.logger.debug('Flushed %d stats' % count)
        self.last = now

class Timer(object):
    def __init__(self):
        self.values = []

    def add(self, v):
        # Not much smarts to this. If we're looking at bigger data,
        # then an automatic downsampling would make sense here.
        self.values.append(v)

    def stats(self, period):
        if self.values:
            d = {}
            d['count'] = len(self.values)
            d['rate'] = d['count'] / period
            d['mean'] = mean(self.values)
            self.values.sort()
            d['min'] = percentile(self.values, 0.0)
            d['median'] = percentile(self.values, 0.5)
            d['upper95'] = percentile(self.values, 0.95)
            d['upper99'] = percentile(self.values, 0.99)
            d['max'] = percentile(self.values, 1.0)
            d['stddev'] = stddev(self.values, d['mean'])
            return d
        return None

    def reset(self):
        self.values[:] = []
