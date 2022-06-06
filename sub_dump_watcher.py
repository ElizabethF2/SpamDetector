import bot
import os, time, json

DUMP_FOLDER = 'user_dumps'
URL_TO_WATCH = 'https://www.reddit.com/r/YourSubHere/new.json'
DELAY = 3*60


SEEN = set()


def dump_user_data(user):
  url = f'https://www.reddit.com/user/{user}/overview.json'
  children = []
  page = 0

  while True:
    print('Getting page', page)
    js = bot.api_call(url)
    for child in js['data']['children']:
      children.append(child['data'])

    after = js['data']['after']
    if not after:
      break

    url = f'https://www.reddit.com/user/{user}/overview.json?after={after}'
    page += 1

  with open(os.path.join(DUMP_FOLDER, f'user-data-dump-{user}.json'), 'a') as f:
    f.write(json.dumps(children))


def main_loop():
  while True:
    js = bot.api_call(URL_TO_WATCH)
    posts = [c['data'] for c in js['data']['children']]
    for post in posts:
      id = post['id']
      author = post['author']
      url = post['url']
      is_spam = bot.is_potential_spam_image(url)

      if id not in SEEN:
        print('found', id, is_spam, author)
        if author != '[deleted]' and is_spam:
          dump_user_data(author)
        SEEN.add(id)

    time.sleep(DELAY)


if __name__ == '__main__':
  main_loop()
