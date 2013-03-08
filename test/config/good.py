from flow import Fanin, Fanout
from inputs.zeromq import Zeromq
from filters.json import Json
from outputs.log import Log

with Fanin():
    Zeromq()

Json()

with Fanout():
    Log()
