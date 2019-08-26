import re
from debug import *
from balancehelper import *
from common import *
from flask_rate_limit import *
from validator import isvalid

app = Flask(__name__)
app.debug = True

@app.route('/', methods=['POST'])
@ratelimit(limit=5, per=60)
def get_balance_v2_response():
  request_dict=request.form
  print_debug(("get_balance_v2_response(request_dict)",request_dict),4)

  try:
      addrs_list=request_dict.getlist('addr')
  except KeyError:
      return jsonify({"error":"'addr' field not supplied"})

  if len(addrs_list)<1:
      return jsonify({"error":"This endpoint requires at least 1 address."})
  elif len(addrs_list)>20:
      return jsonify({"error":"This endpoint accepts at most 20 addresses."})

  clean_list=[]
  for addr in addrs_list:
    a = re.sub(r'\W+', '', addr) #check alphanumeric
    if isvalid(a):
      clean_list.append(a)

  return jsonify( get_bulkbalancedata(clean_list) )

