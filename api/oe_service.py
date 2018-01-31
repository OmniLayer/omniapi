#import urlparse
#import os, sys
#import json
#import re
#from msc_apps import *
#from debug import *
#from balancehelper import *
from flask import Flask, request, Response, jsonify, abort, json, make_response
from get_balance import balance_propid


app = Flask(__name__)
app.debug = True

@app.route('/', methods=['get'])
def requeststat_aspx():
  print request.args
  stat=request.args['stat']
  prop=request.args['prop']
  address=request.args['address']

  if stat=='balance':
    bal=balance_propid(address,prop)
    #jsonify encapsulates in a string, just return number
    return bal

  return jsonify({"stat": stat, "prop":prop, "address":address })

