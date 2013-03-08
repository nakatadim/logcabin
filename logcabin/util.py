import yaml
import time
import gevent
from collections import OrderedDict

class ConfigException(Exception):
    pass

def dynamic_class(modname, classname):
    mod = __import__(modname)
    # import returns the top-level module, so recurse to the sub module
    for m in modname.split('.')[1:]:
        mod = getattr(mod, m)
    return getattr(mod, classname)

def construct_yaml_map(loader, node):
    data = OrderedDict()
    value = loader.construct_mapping(node)
    data.update(value)
    return data

yaml.add_constructor(u'tag:yaml.org,2002:omap', construct_yaml_map)

class BroadcastQueue(list):
    """Queue-like object that broadcasts to all child queues."""

    def put(self, obj):
        for q in self:
            q.put(obj)

    def join(self):
        for q in self:
            q.join()

class Periodic(gevent.Greenlet):
    """Greenlet wrapper that periodically makes a callback."""
    
    def __init__(self, period, callback):
        super(Periodic, self).__init__()
        self.period = period
        self.callback = callback

    def _run(self):
        now = time.time()
        next = now + self.period
        while True:
            while next < now:
                next += self.period
            gevent.sleep(next - now)
            self.callback()
            now = time.time()
