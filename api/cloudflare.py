import requests
import datetime
from config import CFID,CFKEY

def getHeaders():
  header = {"Authorization": "Bearer "+str(CFKEY), "Content-Type": "application/json"}
  return header

def cffblock(ip):
  url = 'https://api.cloudflare.com/client/v4/accounts/'+str(CFID)+'/firewall/access_rules/rules'
  header = getHeaders()
  payload = '{"mode":"block","configuration":{"target":"ip","value":"'+str(ip)+'"},"notes":"API Abuse '+str(datetime.datetime.now())+'"}'
  r = requests.post(url,headers=header,data=payload)
  id = 0
  #if r.status_code == 200:
  response = r.json()
  if response['success']:
    id = response['result']['id']
  return {'success':response['success'], 'id':id}

def cffstatus(id):
  url = 'https://api.cloudflare.com/client/v4/accounts/'+str(CFID)+'/firewall/access_rules/rules/'+str(id)
  header = getHeaders()
  r = requests.get(url,headers=header)
  response = r.json()
  return response

def cffunblock(id):
  url = 'https://api.cloudflare.com/client/v4/accounts/'+str(CFID)+'/firewall/access_rules/rules/'+str(id)
  header = getHeaders()
  r = requests.delete(url,headers=header)
  #if r.status_code == 200:
  response = r.json()
  #  if response['success']:
  #    success = response['success']
  return response

def cffgetAll():
   url = 'https://api.cloudflare.com/client/v4/accounts/'+str(CFID)+'/firewall/access_rules/rules?per_page=1000'
   header = getHeaders()
   r = requests.get(url,headers=header)
   response = r.json()
   return response
