#import urlparse
#import os, sys
#import json
import re
from debug import *
from balancehelper import *
from common import *
from flask_rate_limit import *

app = Flask(__name__)
app.debug = True

@app.route('/', methods=['POST'])
@ratelimit(limit=5, per=60)
def get_balance_v2_response():
  request_dict=request.form
  print_debug(("get_balance_response(request_dict)",request_dict),4)

  try:
      addrs_list=request_dict['addr']
  except KeyError:
      return jsonify({"error":"'addr' field not supplied"})

  if len(addrs_list)<1:
      return jsonify({"error":"This endpoint requires at least 1 address."})
  elif len(addrs_list)>20:
      return jsonify({"error":"This endpoint accepts at most 20 addresses."})

  clean_list=[]
  for addr in addrs_list:
    clean_list.append(re.sub(r'\W+', '', addr)) #check alphanumeric

  return jsonify( get_bulkbalancedata(clean_list) )

