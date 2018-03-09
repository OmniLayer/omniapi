#import urlparse
import re
#from flask import Flask, request, jsonify, abort, json, make_response
from flask_rate_limit import *
from sqltools import *
import json
from transaction_service import gettxjson
from get_balance import balance_full

app = Flask(__name__)
app.debug = True

@app.route('/', methods=['POST'])
@ratelimit(limit=15, per=60)
def search():
  try:
      query = re.sub(r'\W+', '', request.form['query'] ) # strip and get query
  except:
      return jsonify({ 'status': 400, 'data': 'Invalid/No query found in request' })


  asset=[]
  adrbal={}
  txj={}


  if query.isdigit():
    asset=dbSelect("select PropertyID, propertyname,Issuer from smartproperties where PropertyID = " + str(query) + " and protocol='Omni' order by propertyid limit 10")
  else:
    asset=dbSelect("select PropertyID, propertyname,Issuer from smartproperties where (LOWER(PropertyName) like LOWER(\'%" + str(query) + "%\') or LOWER(issuer) like LOWER(\'%" + str(query) + "%\')) and protocol='Omni' order by propertyid limit 10")
    if 25 < len(query) < 45 :
      adrbal=balance_full(query)
    elif len(query) == 64:
      txj = gettxjson(query)
    else:
      return jsonify({ 'status': 400, 'data': 'Search requires either txid or address' })

  return jsonify({ 'status': 200, 'data':{'tx':txj, 'address':adrbal, 'asset':asset}})




def legsearch():
  if 'query' in request.args:
      query = re.sub(r'\W+', '0', request.args.get('query') ) # strip and get query
  else:
      return jsonify({ 'status': 400, 'data': 'No query found in request' })
  ROWS=dbSelect("select txj.txdata from transactions t, txjson txj where t.txhash ~* \'" + str(query) + "\' and t.txdbserialnum=txj.txdbserialnum limit 10")

  response = []
  if len(ROWS) > 0:
    for queryrow in ROWS:
      try:
        txJson = json.loads(queryrow[0])
      except TypeError:
        txJson = queryrow[0]
      response.append(txJson)

  return jsonify({ 'status': 200, 'data': response })
