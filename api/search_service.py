#import urlparse
import re
from flask import Flask, request, jsonify, abort, json, make_response
from sqltools import *
import json
#import requests, glob

app = Flask(__name__)
app.debug = True

@app.route('/', methods=['GET'])
def search():
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
