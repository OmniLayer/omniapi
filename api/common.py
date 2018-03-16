import urlparse
import os, sys, pybitcointools, bitcoinrpc, getpass
from bitcoin_tools import *
from sqltools import *
from rpcclient import *
from cacher import *

http_status = '200 OK'

def response_with_error(start_response, environ, response_body):
    headers = [('Content-type', 'application/json')]
    start_response(http_status, headers)
    response='{"error":"'+response_body+'"}'
    return response

def general_handler(environ, start_response, response_dict_to_response_func):
    path    = environ['PATH_INFO']
    method  = environ['REQUEST_METHOD']
    http_status = 'invalid'
    response_status='OK'
    if method != 'POST':
        return response_with_error(start_response, environ, 'No POST')
    else:
        try:
            request_body_size = int(environ['CONTENT_LENGTH'])
            request_body = environ['wsgi.input'].read(request_body_size)
        except (TypeError, ValueError):
            return response_with_error(start_response, environ, 'Bad environ in POST')
        try:
            response_dict=urlparse.parse_qs(request_body)
        except (TypeError, ValueError):
            return response_with_error(start_response, environ, 'Bad urlparse')

        (response, error)=response_dict_to_response_func(response_dict)
        if error != None:
            return response_with_error(start_response, environ, error)

        headers = [('Content-type', 'application/json')]
        start_response(http_status, headers)
        return response


def raw_revision():
  ckey="info:stats:revision"
  try:
    response = json.loads(lGet(ckey))
    print_debug(("cache looked success",ckey),7)
  except:
    print_debug(("cache looked failed",ckey),7)
    ROWS=dbSelect("select blocknumber, blocktime from blocks order by blocknumber desc limit 1")
    response = {'last_block': ROWS[0][0], 'last_parsed': str(ROWS[0][1])}
    #cache 1 min
    lSet(ckey,json.dumps(response))
    lExpire(ckey,60)
  return response

def isDivisibleProperty(ptype):
  #1: New Indivisible tokens
  #2: New Divisible currency
  #65: Indivisible tokens when replacing a previous property
  #66: Divisible currency when replacing a previous property
  #129: Indivisible tokens when appending a previous property
  #130: Divisible currency when appending a previous property
  if ptype == 2 or ptype == 66 or ptype == 130:
    return True
  else:
    return False

def info(msg):
  func_name='unknown'
  #try:
  #  func_name=inspect.stack()[1][3]
  #except IndexError:
  #  pass
  print '[I] '+func_name+': '+str(msg)
