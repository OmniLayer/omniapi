#from flask import Flask, abort, json, jsonify
from flask_rate_limit import *
#import hashlib
#import pybitcointools
from decimal import Decimal
from rpcclient import *
import re

app = Flask(__name__)
app.debug = True

@app.route('/', methods=['POST'])
@ratelimit(limit=15, per=60)
def decode_handler():
  rawhex = str(re.sub(r'\W+', '', request.form['hex'] ) )
  return jsonify(decode(rawhex))


def getinputs(rawtx):
  retval={'invalid':False, 'inputs':{}}
  for input in rawtx['vin']:
      prevtx=getrawtransaction(input['txid'])
      if prevtx['result']['vout'][input['vout']]['scriptPubKey']['type'] not in ['pubkeyhash','scripthash']:
        #Valid Omni tx's only have pubkeyhash and scripthash as inputs
        retval['invalid']=True
      inputamount= int(Decimal(str( prevtx['result']['vout'][input['vout']]['value']))*Decimal(1e8))
      for addr in prevtx['result']['vout'][input['vout']]['scriptPubKey']['addresses']:
        if addr in retval['inputs']:
          retval['inputs'][addr] += inputamount
        else:
          retval['inputs'][addr] = inputamount
  return retval
  

def decode(rawhex):

  rawBTC = decoderawtransaction(rawhex)['result']
  inputs = getinputs(rawBTC)['inputs']

  try:
    rawOMNI = omni_decodetransaction(rawhex)
    rawOMNI = rawOMNI['result']
    sender  = rawOMNI['sendingaddress']
    try:
      reference = rawOMNI['referenceaddress']
    except:
      reference = ""
  except Exception as e:
    rawOMNI=e.message
    sia=0
    sender=""
    reference=""
    for s in inputs:
      if inputs[s] > sia:
        sender = s
        sia = inputs[s]
        print sia

  if sender == "":
    error = "Can\'t decode Omni TX. No valid sending address found."
  else:
    error = "None"

  print {'Sender':sender,'Reference':reference,'BTC':rawBTC, 'OMNI':rawOMNI,'inputs':inputs, 'error':error}
  return {'Sender':sender,'Reference':reference,'BTC':rawBTC, 'OMNI':rawOMNI,'inputs':inputs, 'error':error}
