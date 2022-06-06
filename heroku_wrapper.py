import os, http.server, threading, json
import bot

print('dbg heroku_wrapper environ is', repr(os.environ))

try:
  PORT = int(os.environ['PORT'])
  print('dbg heroku_wrapper Port set via environ: ' + str(PORT))
except Exception as e:
  PORT = 80
  print('dbg heroku_wrapper Port set to default due to ' + repr(e))

class HerokuRequestHandler(http.server.BaseHTTPRequestHandler):
  def respond(s, type, content):
    s.send_response(200)
    s.send_header('Content-type', type)
    s.end_headers()
    s.wfile.write(content)

  def do_GET(s):
    path = s.path.encode()
    spath = s.path.split('/')
    if len(spath) == 3 and spath[1] == 'is_known_spammer':
      s.respond('application/json', json.dumps(bot.is_known_spammer(spath[2])).encode())
    elif len(spath) == 3 and spath[1] == 'get_user_type':
      s.respond('application/json', json.dumps(bot.get_user_type(spath[2]).name).encode())
    elif s.path == '/dump_user_cache':
      s.respond('application/json', json.dumps({k:v.name for k,v in bot.dump_user_cache().items()}).encode())
    elif len(spath) == 3 and spath[1] == 'check_post_by_id':
      try:
        s.respond('application/json', json.dumps(bot.check_post_by_id(spath[2])).encode())
      except Exception as e:
        s.respond('application/json', json.dumps({'error': e}).encode())
    else:
      s.respond('text/html', b'If you are seeing this page, everything is working.<br><br>Requested Path: ' + path)


def server_thread_worker():
  httpd = http.server.HTTPServer(('', PORT), HerokuRequestHandler)
  httpd.serve_forever()

def main():
  server_thread = threading.Thread(target=server_thread_worker, daemon=True)
  server_thread.start()

  bot.main_loop()

if __name__ == '__main__':
  main()
