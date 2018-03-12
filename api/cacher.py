import config
import redis
import json
from debug import *

#remote server
r = redis.StrictRedis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB)
#local server
l = redis.StrictRedis()

try:
  expTime=config.BTCBAL_CACHE
except:
  expTime=600

def lInit(db):
  try:
    dbk=int(db)
  except:
    dbk=1
  return redis.StrictRedis(db=dbk)

def lGet(key):
  return l.get(key)

def lSet(key,value):
  return l.set(key,value)

def lExpire(key,sec):
  return l.expire(key,sec)

def lDelete(key):
  return l.delete(key)

def lKeys(key):
  return l.keys(key)

def rGet(key):
  return r.get(key)

def rSet(key,value):
  return r.set(key,value)

def rExpire(key,sec):
  return r.expire(key,sec)

def rDelete(key):
  return r.delete(key)

def rKeys(key):
  return r.keys(key)

def rSetNotUpdateBTC(baldata):
  fresh=baldata['fresh']
  if fresh!=None and len(fresh)>0:
    for addr in fresh:
      rSet("omniwallet:balances:address:"+str(addr),json.dumps( {"bal":baldata['bal'][addr],"error":None}))
      rExpire("omniwallet:balances:address:"+str(addr),expTime)

def rExpireAllBalBTC():
  for addr in rKeys("omniwallet:balances:address:*"):
    rDelete(addr)
