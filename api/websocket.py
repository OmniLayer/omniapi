import time, datetime
import json, re, sys
import uuid
import yaml

import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import socket
from threading import Thread

from common import *
from balancehelper import *
from omnidex import getOrderbook
from values_service import getValueBook
from cacher import *
from validator import *
import config


class WSHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        #print 'new connection'
        balance_connect(self)

    def on_message(self, message):
        print_debug(('message received:  %s' % message),4)
        try:
          pmessage = yaml.load(message, Loader=yaml.Loader)
          action = str(pmessage['event'])
        except:
          action = 'unknown'

        try:
          if action == 'subscribe':
            sub = str(pmessage['channel'].lower())
            if sub == 'valuebook':
              if self not in vbs:
                vbs.append(self)
                wsemit('subscribe','valuebook',{'status':'ok'},[self])
              else:
                wsemit('subscribe','valuebook',{'status':'already subscribed'},[self])
            elif sub == 'orderbook':
              if 'pid1' in pmessage and 'pid2' in pmessage:
                try:
                  pair=[int(pmessage['pid1']),int(pmessage['pid2'])]
                  toAdd=[sorted(pair),sorted(pair,reverse=True)]
                  for pair in toAdd:
                    self.obp.append(pair)
                    pid1 = pair[0]
                    pid2 = pair[1]
                    try:
                      obs[pid1][pid2].append(self)
                    except:
                      try:
                        obs[pid1][pid2]=[self]
                      except:
                        obs[pid1]={pid2:[self]}
                  wsemit('subscribe','orderbook',{'status':'ok','pair': sorted(pair)},[self])
                except Exception as e:
                  wsemit('subscribe','orderbook',{'status':'error','pair':pair,'error':str(e)},[self])
              else:
                wsemit('subscribe','orderbook',{'status':'error','error':'missing property id key: pid1 or pid2'},[self])
            elif sub == 'balance':
              try:
                addr = pmessage['data'].replace('"','')
                if ',' in addr:
                  addrlist=addr.split(',')
                  for a in addrlist:
                    add_address(a,self)
                else:
                  if add_address(addr,self):
                    wsemit('subscribe','balance',{'status':'ok'},[self])
              except Exception as e:
                 wsemit('subscribe','balance',{'status':'error', 'error':str(e)},[self])
            else:
              wsemit('subscribe',sub,{'status':'unknown channel'},[self])

          elif action == 'unsubscribe':
            sub = str(pmessage['channel'].lower())
            if sub == 'valuebook':
              if self in vbs:
                vbs.remove(self)
                wsemit('unsubscribe','valuebook',{'status':'ok'},[self])
              else:
                wsemit('subscribe','valuebook',{'status':'not subscribed'},[self])
            elif sub == 'orderbook':
              unsubscribe_orderbook(self,pmessage)
            elif sub == 'balance':
              try:
                addr = pmessage['data']
                if ',' in addr:
                  addrlist=addr.split(',')
                  for a in addrlist:
                    del_address(a,self)
                else:
                  del_address(addr,self)
              except KeyError:
                adl = list(self.addresses)
                for a in adl:
                  del_address(a,self)
              except Exception as e:
                 wsemit('unsubscribe','balance',{'status':'error', 'error':str(e)},[self])
            else:
              wsemit('unsubscribe',sub,{'status':'unknown channel'},[self])

          elif action == 'ping':
            wsemit('ping','info',{'status':'ok','data':'pong'},[self])

          elif action == 'logout':
            disconnect(self)
          else:
            wsemit('info','unsupported request',{'status':'error', 'error':str(message)},[self])
        except Exception as e:
          wsemit('info','unknown',{'status':'error','error':str(e)},[self])

    def on_close(self):
        #print 'connection closed'
        disconnect(self)

    def check_origin(self, origin):
        return True

application = tornado.web.Application([
    (r'/ws', WSHandler),
])


#threads
watchdog = None
emitter = None
bthread = None
vthread = None
othread = None
#stat trackers
clients = 0
maxclients = 0
maxaddresses = 0
#data
addresses = {}
orderbook = {}
lasttrade = 0
lastpending = 0
valuebook = {}
#websocket connections
users = []
abs = {} #addressbook subscribers { '<address>':[users]}
vbs = [] #valuebook subscribers
obs = {} #orderbook subscribers { [pid1]: {[pid2]: [users]} }

#check for testnet setup
try:
 if config.TESTNET == 1:
   TESTNET = True
 else:
   TESTNET = False
except:
  TESTNET = False

def get_real_address(session):
  ret=session.request.remote_ip
  try:
    if session.request.headers['X-Forwarded-For'] is not None:
      addr=session.request.headers['X-Forwarded-For'].split(",")
      ret=addr[0]
  except Exception as e:
      print_debug(('error getting real address',session.id,e),4)
  return ret

def update_balances():
  global addresses, balances

  try:
    while True:
      time.sleep(10)
      print_debug(("updating balances"),7)
      balances=rGet("omniwallet:balances:balbook"+str(config.REDIS_ADDRSPACE))
      if balances != None:
        print_debug(("Balances loaded from redis"),7)
        balances=json.loads(balances)
      else:
        print_debug(("Could not load balances from redis, falling back"),7)
        balances=get_bulkbalancedata(addresses)

      for addr in list(addresses):
        if addresses[addr] < 1 and addresses[addr] >= -30:
          addresses[addr] -= 1
          #cache old addresses for 5~10 minutes after user discconects
        elif addresses[addr] < -30:
          addresses.pop(addr)
      rSet("omniwallet:balances:addresses"+str(config.REDIS_ADDRSPACE),json.dumps(addresses))
  except Exception as e:
    print_debug(("error updating balances:",str(e)),4)

def update_orderbook():
  global orderbook, lasttrade, lastpending

  try:
    while True:
      time.sleep(10)
      print_debug(("updating orderbook"),4)
      ret=getOrderbook(lasttrade, lastpending)
      print_debug(("Checking for new orderbook updates, last:",str(lasttrade)),4)
      if ret['updated']:
        orderbook=ret['book']
        print_debug(("Orderbook updated. Lasttrade:",str(lasttrade),"Newtrade:",str(ret['lasttrade']),"Book length is:",str(len(orderbook))),4)
        lasttrade=ret['lasttrade']
        lastpending=ret['lastpending']
  except Exception as e:
    print_debug(("error updating orderbook:",str(e)),4)

def update_valuebook():
  global valuebook

  try:
    pmaxid=0
    while True:
      time.sleep(30)
      print_debug(("updating valuebook"),4)
      vbook,maxid=getValueBook(pmaxid)
      if len(vbook)>0:
        pmaxid=maxid
        for v in vbook:
          name=v[0]
          p1=v[1]
          pid1=int(v[2])
          p2=v[3]
          pid2=int(v[4])
          rate=v[5]
          tstamp=str(v[6])
          source=v[7]
          if p1=='Bitcoin' and p2=='Omni':
            if pid2==1:
              symbol="OMNI"
            else:
              symbol="SP"+str(pid2)
          elif p1=='Fiat' and p2=='Bitcoin':
            #symbol="BTC"
            #if pid1>0 or pid2>0:
            #  symbol=symbol+str(name)
            symbol="BTC"+str(name)
          else:
            symbol=name+str(pid2)
          valuebook[symbol]={"price":rate,"symbol":symbol,"timestamp":tstamp, "source":source}
  except Exception as e:
    print_debug(("error updating valuebook:",str(e)),4)

def watchdog_thread():
    global emitter, bthread, vthread, othread

    while True:
      try:
        time.sleep(10)
        print_debug(("watchdog running"),4)
        if emitter is None or not emitter.isAlive():
          print_debug(("emitter not running"),4)
          emitter = Thread(target=emitter_thread)
          emitter.daemon = True
          emitter.start()
        if bthread is None or not bthread.isAlive():
          print_debug(("balance thread not running"),4)
          bthread = Thread(target=update_balances)
          bthread.daemon = True
          bthread.start()
        if vthread is None or not vthread.isAlive():
          print_debug(("value thread not running"),4)
          vthread = Thread(target=update_valuebook)
          vthread.daemon = True
          vthread.start()
        if othread is None or not othread.isAlive():
          print_debug(("orderbook not running"),4)
          othread = Thread(target=update_orderbook)
          othread.daemon = True
          othread.start()
      except Exception as e:
        print_debug(("error in watchdog:",str(e)),4)

def wsemit(event, channel, data, filter=None):
    tsm = (datetime.datetime.utcnow() - datetime.datetime(1970,1,1)).total_seconds() * 1000.0
    msg = {
            'event':event, 
            'channel':channel, 
            'response':data,
            'ts':tsm
          }
    if filter is None:
      for user in users:
        try:
          user.write_message(msg)
        except:
          print_debug(("client disconnect"),5)
    else:
      for user in filter:
        try:
          user.write_message(msg)
        except:
          print_debug(("client disconnect"),5)

def emitter_thread():
    #Send data for the connected clients
    count = 0
    while True:
      try:
        time.sleep(15)
        count += 1
        print_debug(("Tracking",str(len(addresses)),"/",str(maxaddresses),"(max) addresses, for",str(clients),"/",str(maxclients),"(max) clients, ran",str(count),"times"),4)
        #push addressbook
        for addr in abs:
          for session in abs[addr]:
            try:
              if addr in balances:
                wsemit('update',"balance",{'address':str(addr),'balance':balances[addr]},[session])
              else:
                print_debug((addr,"balance not loaded yet"),4)
            except Exception as e:
              print_debug(("error pushing balance data for",addr,str(e)),4)
        #push valuebook
        wsemit('update','valuebook',{'data':valuebook},vbs)
        #push orderbook
        for pid1 in obs.keys():
          for pid2 in obs[pid1]:
            for session in obs[pid1][pid2]:
              try:
                obdata = orderbook[pid1][pid2]
                msg = {pid1:{pid2:obdata}}
                wsemit('update','orderbook',{'data':msg},[session])
              except:
                pass
        #Heartbeat
        wsemit('info','session','hb')
      except Exception as e:
        print_debug(("emitter error:",str(e)),4)

#@socketio.on('connect', namespace='/balance')
def balance_connect(session):
    global users, clients, maxclients, watchdog

    session.id = str(uuid.uuid4())
    session.addresses=[]
    session.obp=[]
    users.append(session)
    print_debug(('Client connected',session.id),4)

    clients += 1
    if clients > maxclients:
      maxclients=clients

    if watchdog is None or not watchdog.isAlive():
        watchdog = Thread(target=watchdog_thread)
        watchdog.daemon = True
        watchdog.start()
    wsemit('info','session',{'status':'connected','id':str(session.id)},[session])

def endSession(session):
  global addresses, abs, vbs

  try:
    for address in session.addresses:
      if addresses[address] == 1:
        #addresses.pop(address)
         addresses[address] = -1
      else:
        addresses[address] -= 1
      try:
        abs[str(address)].remove(session)
      except:
        pass
  except KeyError:
    #addresses not defined
    print_debug(("No addresses list to clean for",str(session.id)),4)
  try:
    #remove any valuebook subscribtions
    vbs.remove(session)
  except:
    pass
  try:
    #remove any orderbook subscribtions
    #obs.remove(session)
    unsubscribe_orderbook(session)
  except:
    pass


#@socketio.on('disconnect', namespace='/balance')
def disconnect(session):
    global clients, users

    print_debug(('Client disconnected',session.id),4)
    clients -=1
    #make sure we don't screw up the counter if reloading mid connections
    if clients < 0:
      clients=0
    endSession(session)
    users.remove(session)


#@socketio.on("address:add", namespace='/balance')
def add_address(address,session):
  global addresses, abs, vbs, maxaddresses

  address=str(address)

  if isvalid(address):
    pass
  else:
    wsemit('subscribe','balance',{'address':address,'status':'invalid address'}, [session])
    return False

  if address not in session.addresses:
    session.addresses.append(address)
    if address in addresses and addresses[address] > 0:
      addresses[address] += 1
    else:
      addresses[address] = 1

    rSet("omniwallet:balances:addresses"+str(config.REDIS_ADDRSPACE),json.dumps(addresses))
    #speed up initial data load
    balance_data=get_balancedata(address)
    wsemit('subscribe','balance',{'address':address,'status':'ok'}, [session])
    wsemit('update','balance',{'address':address, 'balance':balance_data}, [session])

    try:
      abs[address].append(session)
    except:
      abs[address] = [session]
  #if session not in vbs:
  #  #add session to valuebook
  #  vbs.append(session)
  if len(addresses) > maxaddresses:
    maxaddresses=len(addresses)
  return True


def del_address(address,session):
  global addresses, abs, vbs

  address=str(address)
  if address in session.addresses:
    session.addresses.remove(address)
    if addresses[address] == 1:
       addresses[address] = -1
    else:
      addresses[address] -= 1
    try:
      abs[str(address)].remove(session)
    except:
      pass
    wsemit('unsubscribe','balance',{'address':address, 'status':'ok'}, [session])
  else:
    wsemit('unsubscribe','balance',{'address':address, 'status':'not subscibed'}, [session])
  if len(session.addresses)==0:
    if session in vbs:
      vbs.remove(session)

#@socketio.on("address:refresh", namespace='/balance')
def refresh_address(address,session):
  address=str(address)
  if address in addresses:
    balance_data=get_balancedata(address)
    wsemit('update','balance',{'address':address,'balance':balance_data},[session])
  else:
    add_address(address,[session])

def unsubscribe_orderbook(session,pmessage={}):
  global obs

  if 'pid1' in pmessage and 'pid2' in pmessage:
    try:
      pair=[int(pmessage['pid1']),int(pmessage['pid2'])]
      toRemove=[sorted(pair),sorted(pair,reverse=True)]
      for pair in toRemove:
        session.obp.remove(pair)
        pid1 = pair[0]
        pid2 = pair[1]
        try:
          obs[pid1][pid2].remove(session)
          wsemit('unsubscribe','orderbook',{'status':'ok','pair':pair},[session])
        except:
          wsemit('unsubscribe','orderbook',{'status':'error','pair':pair,'error':'not subscribed'},[session])
    except Exception as e:
      wsemit('unsubscribe','orderbook',{'status':'error','error':str(e)},[session])
  else:
    for pair in session.obp:
      pid1 = pair[0]
      pid2 = pair[1]
      try:
        obs[pid1][pid2].remove(session)
        wsemit('unsubscribe','orderbook',{'status':'ok','pair':pair},[session])
      except:
        pass
    session.obp=[]


if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(1091)
    myIP = socket.gethostbyname(socket.gethostname())
    print_debug(('*** Websocket Server Started on %s***' % myIP),4)
    try:
      tornado.ioloop.IOLoop.instance().start()
    except (KeyboardInterrupt, SystemExit):
      print_debug(('*** Websocket Server Stopping on %s***' % myIP),4)
      tornado.ioloop.IOLoop.instance().stop()
      sys.exit()
