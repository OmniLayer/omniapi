import urlparse
import os, sys
import json
import re
from msc_apps import *
from debug import *
from balancehelper import *
from flask import Flask, request, Response, jsonify, abort, json, make_response

app = Flask(__name__)
app.debug = True

@app.route('/', methods=['POST'])
def get_balance_response():
  request_dict=request.form
  print "get_balance_response(request_dict)",request_dict

  try:
      addrs_list=request_dict['addr']
  except KeyError:
      return jsonify({"error":"'addr' field not supplied"})
  print addrs_list

  if len(request_dict.getlist('addr'))!=1:
      return jsonify({"error":"This endpoint accepts single address lookups. For multiple addresses use the v2 endpoint"})
  return jsonify(balance_full(addrs_list))

def balance_full(addr):
  addr = re.sub(r'\W+', '', addr) #check alphanumeric
  #Use new balance function call
  #return (json.dumps( get_balancedata(addr) ), None)
  return get_balancedata(addr)


def balance_propid(addr,pid):
  bal=balance_full(addr)
  try:
    for x in bal['balance']:
     if x['id']==pid:
       print x
       if x['divisible']:
         return from_satoshi(x['value'])
       else:
         return x['value']
    return '0'
  except Exception as e:
    print "error getting bal for "+str(addr)+" "+str(e)
    return '0'
