from flask import Flask, request, Response, jsonify, abort, json, make_response
from bitcoin_tools import *
from get_balance import balance_propid
from transaction_service import gettxjson, getblocktxjson, getaddrhist

app = Flask(__name__)
app.debug = True

@app.route('/requeststat.aspx', methods=['get'])
def requeststat_aspx():
  print request.args
  args=request.args
  if 'stat' not in args:
    return jsonify({"error":"invalid request"})

  stat=args['stat']

  if stat=='balance':
    if 'prop' not in args or 'address' not in args:
      return jsonify({"error":"invalid request"})

    prop=args['prop']
    address=args['address']
    if is_valid_bitcoin_address(address):
      bal=balance_propid(address,prop)
      #jsonify encapsulates in a string, just return number
      return bal
    else:
      return jsonify({"error":"invalid address"})
  elif stat=='gettx':
    if 'txid' not in args:
      return jsonify({"error":"invalid request, missing txid"})
    return jsonify(gettxjson(args['txid']))
  elif stat=='getblocktx':
    if 'block' not in args:
      return jsonify({"error":"invalid request, missing block"})
    return jsonify(getblocktxjson(args['block']))
  else:
    return jsonify({"error":"unsupported call","args": args })


@app.route('/ask.aspx', methods=['get'])
def ask_aspx():
  print request.args
  args=request.args
  if "api" not in args:
    return jsonify({"error":"invalid request"})

  api=args['api']
  if api=="getrecipienthistory":
    if 'address' not in args:
      return jsonify({"error":"invalid request"})

    address=args['address']
    if is_valid_bitcoin_address(address):
      return jsonify( getaddrhist(address,'receive'))
    else:
      return jsonify({"error":"invalid address"})
  elif api=="getsenderhistory":
    if 'address' not in args:
      return jsonify({"error":"invalid request"})

    address=args['address']
    if is_valid_bitcoin_address(address):
      return jsonify( getaddrhist(address,'send'))
    else:
      return jsonify({"error":"invalid address"})
  else:
    return jsonify({"error":"unsupported call", "args": args })
