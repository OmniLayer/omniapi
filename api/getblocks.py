import os, sys, re, random
import requests
from decimal import Decimal
#from flask import Flask, request, jsonify, abort, json, make_response
from flask_rate_limit import *
from common import *
from cacher import *
from debug import *

app = Flask(__name__)
app.debug = True

@app.route('/getlast', methods=['POST'])
@ratelimit(limit=20, per=60)
def getlast():
    try:
        origin = request.form['origin']
    except KeyError:
        abort(make_response('No field \'origin\' in request, request failed', 400))

    if origin == "blockchain":
      ckey="info:block:blockchain"
      try:
        #check cache
        block = json.loads(ckey)
        print_debug(("cache looked success",ckey),7)
      except:
        print_debug(("cache looked failed",ckey),7)
        try:
          data = requests.get('https://blockchain.info/latestblock', timeout=10)
          block = data.json()
          #cache for 1 min
          lSet(ckey,json.dumps(block))
          lExpire(ckey,60)
        except requests.exceptions.RequestException:
          abort(make_response('Query Timeout in request, request failed', 400))
      return jsonify(block)
    else:
        abort(make_response('Unsupported origin', 400))
