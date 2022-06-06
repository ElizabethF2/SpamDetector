# -*- coding: utf-8 -*-

import urllib.parse, urllib.request, html, json, time, re, os, enum, io, threading, ssl, http, functools, socket, base64, sys
from PIL import Image, ImageOps, ImageDraw, UnidentifiedImageError

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
  sys.path.append(SCRIPT_DIR)

import imagehash_no_numpy as imagehash

DRY_RUN = False
POST_MESSAGE = False
RETRY_COUNT = 5
MAX_IMAGE_SIZE = 2500
DOWNLOAD_TIMEOUT = 30

SAME_SUB_HASH_DELTA_THRESHOLD = 10
DIFFERENT_SUB_HASH_DELTA_THRESHOLD = 7
BANNER_PIXEL_DELTA_THRESHOLD = 40
MIN_POST_COUNT = 10

REDDIT_USERNAME = config.get('username')
REDDIT_PASSWORD = config.get('password')
REDDIT_CLIENTID = config.get('clientid')
REDDIT_CLIENTSECRET = config.get('clientsecret')

REDDIT_BASE = 'https://reddit.com'

def dprint(*msgs):
  print(*msgs)

def get_user_type(user):
  try:
    return _USER_CACHE[user]
  except KeyError:
    return UserType.Unknown


def is_known_spammer(user):
  return get_user_type(user) not in {UserType.Unknown, UserType.NotASpammer}


def dump_user_cache():
  return _USER_CACHE

def web_request(method, url, headers, data=None, ssl_verify=True):
  req = urllib.request.Request(url, headers=headers, data=data)
  req.method = method
  if ssl_verify:
    res = urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT)
  else:
    cxt = ssl.SSLContext()
    res = urllib.request.urlopen(req, context=cxt, timeout=DOWNLOAD_TIMEOUT)
  return res.read()

def api_call(url, method='GET', do_sleep=True, decode_json=True, ssl_verify=True, user_agent = USER_AGENT):
  dprint('  dbg api_call', url)
  for i in range(RETRY_COUNT):
    try:
      if do_sleep:
        time.sleep(5) # Avoids rate limits
      res = web_request(method, url, {'user-agent': user_agent}, ssl_verify = ssl_verify)
      if decode_json:
        return json.loads(res)
      return res
    except (TimeoutError, urllib.error.URLError) as ex:
      e = ex
      if isinstance(e, urllib.request.HTTPError):
        if e.status >= 400 and e.status < 500:
          raise e
      dprint('  dbg failed attempt', i, 'with', type(e))
      time.sleep(30)
  raise e

class Reddit(object):
  def __init__(self):
    self.token_expiration = 0

  def ensure_authenticated(self):
    if time.time() >= self.token_expiration:
      headers = {'user-agent': USER_AGENT,
                 'authorization': 'Basic ' + base64.b64encode((REDDIT_CLIENTID+':'+REDDIT_CLIENTSECRET).encode('UTF8')).decode(),
                 'content-type': 'application/x-www-form-urlencoded'}
      data = urllib.parse.urlencode({'grant_type': 'password', 'username': REDDIT_USERNAME, 'password': REDDIT_PASSWORD}).encode()
      resp = json.loads(web_request('POST', 'https://www.reddit.com/api/v1/access_token', headers, data=data))
      self.token_type = resp.get('token_type')
      self.access_token = resp.get('access_token')
      self.token_expiration = time.time() + resp.get('expires_in')

  def authenticated_api_call(self, method, path, body=None):
    self.ensure_authenticated()
    headers = {'user-agent': USER_AGENT,
               'authorization': self.token_type + ' ' + self.access_token}
    if body:
      data = json.dumps(body).encode()
      headers['content-type'] = 'application/json'
    else:
      data = None
    return json.loads(web_request(method, 'https://oauth.reddit.com/'+path, headers, data=data))

  def get_post_or_comment(self, id):
    return self.authenticated_api_call('GET', 'comments/' + id, {'limit': 2048, 'sort': 'confidence', 'raw_json': 1})[0]['data']['children'][0]['data']

  def downvote(self, id):
    self.authenticated_api_call('POST', 'api/vote?api_type=json&dir=-1&id='+id, None)

  def report(self, id, reason):
    self.authenticated_api_call('POST', 'api/report', {'api_type': 'json', 'id': id, 'reason': reason})

  def remove(self, id):
    raise Exception('TODO Implement Me!')

  def reply(self, id, message):
    raise Exception('TODO Implement Me!')


reddit = Reddit()


COLOR_WHITE = (255,255,255,0)


def get_bound(image, start, step, color = COLOR_WHITE):
  x, y = start
  while x >= 0 and y >= 0 and x < image.width and y < image.height:
    if image.getpixel((x, y)) != color[:3]:
      return x,y
    
    x += step[0]
    y += step[1]
  
  return start


def unrotate(image, angle=10):
  restored_image = image.rotate(angle, Image.NEAREST, expand = 1, fillcolor = COLOR_WHITE)
  left = get_bound(restored_image, (0, restored_image.height//2), (1,0))[0]
  right = get_bound(restored_image, (restored_image.width-1, restored_image.height//2), (-1,0))[0]
  top = get_bound(restored_image, (restored_image.width//2, 0), (0,1))[1]
  bottom = get_bound(restored_image, (restored_image.width//2, restored_image.height-1), (0,-1))[1]
  return restored_image.crop((left, top, right, bottom))


def get_image(url):
  data = web_request('GET', url, {'user-agent': PC_USER_AGENT})
  image = Image.open(io.BytesIO(data))
  if image.width > MAX_IMAGE_SIZE:
    h = (MAX_IMAGE_SIZE*image.height)//image.width
    image = image.resize((MAX_IMAGE_SIZE, h))
  if image.height > MAX_IMAGE_SIZE:
    w = (MAX_IMAGE_SIZE*image.width)//image.height
    image = image.resize((w, MAX_IMAGE_SIZE))
  if image.mode != 'RGB':
    image = image.convert('RGB')
  return image


@functools.lru_cache(maxsize=1)
def get_image_cached(url):
  return get_image(url)

def pixel_delta(a, b):
  return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])

@functools.lru_cache
def get_user_posts_cached(user):
  return [post['data'] for post in api_call(f'https://www.reddit.com/user/{user}/submitted.json')['data']['children']]

def check_all_subreddits():
  for sub in SUBS_TO_CHECK:
    js = api_call(f'https://www.reddit.com/r/{sub}/new.json')
    for post in js['data']['children']:
      check_post(post['data'])

def check_all_users():
  dprint('  dbg check_all_users accounts', SPAM_ACCOUNTS)
  for user in list(SPAM_ACCOUNTS):
    try:
      js = api_call(f'https://www.reddit.com/user/{user}/submitted.json?sort=new')
      for post in (p['data'] for p in js['data']['children']):
        if post['id'] not in _already_checked_posts:
          old_type = get_user_type(user)
          check_post(post)
          if not is_known_spammer(user):
            assert(old_type != UserType.Unknown)
            _USER_CACHE[user] = old_type
    except urllib.error.HTTPError as ex:
      if ex.code in (403, 404):
        SPAM_ACCOUNTS.remove(user)
      else:
        raise ex

def main_loop():
  while True:
    check_all_subreddits()
    check_all_users()
    time.sleep(1.5*60)

def check_post_by_id(id, silent = None):
  post = api_call(REDDIT_BASE+'/'+id+'.json', do_sleep=False)[0]['data']['children'][0]['data']

  if post['id'] in _already_checked_posts:
    return is_known_spammer(post['author'])

  if silent is None:
    silent = post['subreddit'] not in SUBS_TO_CHECK
  return check_post(post, silent = silent)

def check_post_by_url(url):
  post = api_call(url+'.json', do_sleep=False)[0]['data']['children'][0]['data']
  return check_post(post)

def id_from_url(url):
  sp = url.split('/')
  try:
    return sp[sp.index('comments')+1]
  except ValueError:
    return sp[-1]

def url_from_id(id):
  return REDDIT_BASE + '/' + id

if __name__ == '__main__':
  main_loop()
