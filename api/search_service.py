#import urlparse
import re
#from flask import Flask, request, jsonify, abort, json, make_response
from flask_rate_limit import *
from sqltools import *
import json
from transaction_service import gettxjson
from get_balance import balance_full
from cacher import *
from debug import *

app = Flask(__name__)
app.debug = True

@app.route('/', methods=['POST'])
@ratelimit(limit=15, per=60)
def search():
  try:
      query = re.sub(r'\W+', '', request.form['query'] ) # strip and get query
  except:
      return jsonify({ 'status': 400, 'data': 'Invalid/No query found in request' })

  ckey="data:search:"+str(query)
  try:
    response = json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    asset=[]
    adrbal={}
    txj={}


    if query.isdigit():
      if int(query) == 1:
        asset=dbSelect("select PropertyID, propertyname,Issuer,flags from smartproperties where ecosystem='Production' and protocol='Omni' order by propertyid")
      elif int(query) == 2:
        asset=dbSelect("select PropertyID, propertyname,Issuer,flags from smartproperties where ecosystem='Test' and protocol='Omni' order by propertyid")
      else:
        asset=dbSelect("select PropertyID, propertyname,Issuer,flags from smartproperties where PropertyID = %s and protocol='Omni' order by propertyid limit 10",[str(query)])
    else:
      wq='%'+str(query)+'%'
      asset=dbSelect("select PropertyID, propertyname,Issuer,flags from smartproperties where (LOWER(PropertyName) like LOWER(%s) or LOWER(issuer) like LOWER(%s)) and protocol='Omni' order by propertyid limit 10",(wq,wq))
      if 25 < len(query) < 45 :
        adrbal=balance_full(query)
        if 'balance' in adrbal and 'Error' in adrbal['balance']:
          adrbal = {}
      elif len(query) == 64:
        txj = gettxjson(query)
        if 'type' in txj and 'Error' in txj['type']:
          txj = {}
      else:
        pass
    response={ 'status': 200, 'query':query, 'data':{'tx':txj, 'address':adrbal, 'asset':asset} }
    #cache for 5 min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,300)

  return jsonify(response)


def legsearch():
  if 'query' in request.args:
      query = re.sub(r'\W+', '0', request.args.get('query') ) # strip and get query
  else:
      return jsonify({ 'status': 400, 'data': 'No query found in request' })
  ROWS=dbSelect("select txj.txdata from transactions t, txjson txj where t.txhash ~* %s and t.txdbserialnum=txj.txdbserialnum limit 10",[str(query)])

  response = []
  if len(ROWS) > 0:
    for queryrow in ROWS:
      try:
        txJson = json.loads(queryrow[0])
      except TypeError:
        txJson = queryrow[0]
      response.append(txJson)

  return jsonify({ 'status': 200, 'data': response })
