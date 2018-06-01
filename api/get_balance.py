#import urlparse
#import os, sys
#import json
import re
#from msc_apps import *
from debug import *
from bitcoin_tools import *
from balancehelper import *
from common import *
from cacher import *
from transaction_service import getaddresshistraw
#from flask import Flask, request, Response, jsonify, abort, json, make_response
from flask_rate_limit import *

app = Flask(__name__)
app.debug = True

@app.route('/', methods=['POST'])
@ratelimit(limit=20, per=60)
def get_balance_response():
  request_dict=request.form
  print_debug(("get_balance_response(request_dict)",request_dict),4)

  try:
      addrs_list=request_dict['addr']
  except KeyError:
      return jsonify({"error":"'addr' field not supplied"})
  print_debug(addrs_list,4)

  if len(request_dict.getlist('addr'))!=1:
      return jsonify({"error":"This endpoint accepts single address lookups. For multiple addresses use the v2 endpoint"})
  return jsonify(balance_full(addrs_list))

@app.route('/details/', methods=['POST'])
@ratelimit(limit=20, per=60)
def addressDetails():
    try:
        address = str(re.sub(r'\W+', '', request.form['addr'] ) ) #check alphanumeric
    except ValueError:
        abort(make_response('This endpoint only consumes valid input', 400))

    try:
      page=int(request.form['page'])
    except:
      page=0

    baldata=get_balancedata(address)
    txdata = getaddresshistraw(address,page)

    txdata['balance'] = baldata['balance']
    return jsonify(txdata)

def balance_full(addr):
  rev=raw_revision()
  cblock=rev['last_block']

  addr = re.sub(r'\W+', '', addr) #check alphanumeric
  ckey="data:addrbal:"+str(addr)+":"+str(cblock)
  try:
    #check cache
    baldata = json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    #Use new balance function call
    baldata=get_balancedata(addr)
    lSet(ckey,json.dumps(baldata))
    lExpire(ckey,30)
    #cache for 30seconds
  return baldata


def balance_propid(addr,pid):
  bal=balance_full(addr)
  try:
    for x in bal['balance']:
     if x['id']==pid:
       print_debug(x,4)
       if x['divisible']:
         return from_satoshi(x['value'])
       else:
         return x['value']
    return '0'
  except Exception as e:
    print_debug(("error getting bal for ",addr,e),2)
    return '0'
