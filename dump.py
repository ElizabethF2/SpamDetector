import urllib.request, json, time

def web_request(url):
  print('  dbg web_request', url)
  time.sleep(2) # Avoids rate limits
  req = urllib.request.Request(url, headers={'user-agent': 'spam account detector bot test'})
  req.method = 'GET'
  res = urllib.request.urlopen(req)
  return res.read()


def api_call(url):
  return json.loads(web_request(url))


def dump_user_data(user):
  url = f'https://www.reddit.com/user/{user}/overview.json'
  children = []
  page = 0

  while True:
    print('Getting page', page)
    js = api_call(url)
    for child in js['data']['children']:
      children.append(child['data'])

    after = js['data']['after']
    if not after:
      break

    url = f'https://www.reddit.com/user/{user}/overview.json?after={after}'
    page += 1

  with open(f'user-data-dump-{user}.json', 'a') as f:
    f.write(json.dumps(children))

print('Enter username to dump data for:')
u = input('> ')
dump_user_data(u)
