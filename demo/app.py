#coding=utf8
__author__ = 'Alexander.Li'
import sys
sys.path.append("..")
import os
import time
import logging
import tornado.auth
import tornado.escape
import tornado.ioloop
import tornado.web
from tornado import gen
from TorCast import client

settings = {
    "template_path" : os.path.join(os.path.dirname(__file__), "template"),
    "gzip" : True,
    "debug" : True,
    "cookie_secret" : "xxxxxooooo",
    "login_url" : "/auth/login"
}

class Chatroome(object):
    def __init__(self):
        self.user_handler = {}
        self.user_messages = {}
        self.global_messages = []

    def wait_message(self, user_id, ts, handler):
        if user_id in self.user_messages:
            ts_now = int(time.time()*1000)
            pool = self.user_messages[user_id]
            if pool:
                lost_messages = [ msg[1] for msg in pool if msg[0]> ts ]
                if lost_messages:
                    handler.write(tornado.escape.json_encode(dict(messages=lost_messages, ts=ts_now)))
                    handler.finish()
                    del self.user_messages[user_id]
                    return
                del self.user_messages[user_id]
        self.user_handler[user_id] = handler


    def say_to_all(self, message):
        ts = int(time.time()*1000)
        self.global_messages.append(message)
        if len(self.global_messages)>50:
            self.global_messages=self.global_messages[:-50]
        for user_id , handler in self.user_handler.iteritems():
            try:
                handler.write(tornado.escape.json_encode(dict(messages=[message,],ts=ts)))
                handler.finish()
                del self.user_messages[user_id]
            except Exception, e:
                if user_id in self.user_messages:
                    pool = self.user_messages[user_id]
                    pool.append((ts, message))
                else:
                    self.user_messages[user_id] = [(ts, message),]



class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie("chatdemo_user")
        if not user_json: return None
        return tornado.escape.json_decode(user_json)

class MainHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        messages = chatroom.global_messages
        messages.reverse()
        self.render("index.html",messages=messages,user=self.current_user)


class MessageFetcher(BaseHandler):

    @tornado.web.asynchronous
    def get(self):
        user_id = self.current_user["claimed_id"]
        ts = self.get_argument("ts")
        chatroom.wait_message(user_id, int(ts), self)


    @tornado.web.authenticated
    def post(self):
        import cgi
        user = self.current_user
        message = self.get_argument("message")[:144]
        sub.notify_all("chatroom", u"%s:%s"%(user["name"], cgi.escape(message)))
        self.finish(tornado.escape.json_encode(dict(rs=True)))


class AuthLoginHandler(tornado.web.RequestHandler, tornado.auth.GoogleMixin):
    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        if self.get_argument("openid.mode", None):
            user = yield self.get_authenticated_user()
            self.set_secure_cookie("chatdemo_user",
                                   tornado.escape.json_encode(user))
            self.redirect("/")
            return
        self.authenticate_redirect(ax_attrs=["name"])


class AuthLogoutHandler(tornado.web.RequestHandler):
    def get(self):
        self.clear_cookie("chatdemo_user")
        self.write("You are now logged out")

application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/auth/login", AuthLoginHandler),
    (r"/auth/logout", AuthLogoutHandler),
    (r"/message", MessageFetcher),
],**settings)

def on_message(chn, data):
    chatroom.say_to_all(data)

if __name__ == "__main__":
    application.listen(int(sys.argv[1]))
    sub = client.Subscriber("127.0.0.1", 6379, 5)
    chatroom = Chatroome()
    sub.listen_on(["chatroom",], on_message)
    tornado.ioloop.IOLoop.instance().start()
