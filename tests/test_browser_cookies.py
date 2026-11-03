import unittest
from unittest.mock import patch
from types import SimpleNamespace
from http.cookiejar import Cookie, CookieJar
from bilitv_downloader import load_browser_cookies, make_session


def cookie(domain, name):
    return Cookie(version=0, name=name, value='secret', port=None, port_specified=False,
                  domain=domain, domain_specified=True, domain_initial_dot=domain.startswith('.'),
                  path='/', path_specified=True, secure=True, expires=None, discard=True,
                  comment=None, comment_url=None, rest={}, rfc2109=False)

class BrowserCookieTests(unittest.TestCase):
    def test_reject_unknown_browser(self):
        with self.assertRaises(ValueError):
            load_browser_cookies(make_session(), 'other')
    def test_only_bilibili_cookies(self):
        jar = CookieJar()
        jar.set_cookie(cookie('.bilibili.tv', 'sid'))
        jar.set_cookie(cookie('.example.com', 'other'))
        with patch.dict('sys.modules', {'browser_cookie3': SimpleNamespace(chrome=lambda **kw: jar)}):
            session = make_session()
            self.assertEqual(load_browser_cookies(session, 'chrome'), 1)
            self.assertEqual([c.name for c in session.cookies], ['sid'])
    def test_empty_cookie_jar(self):
        with patch.dict('sys.modules', {'browser_cookie3': SimpleNamespace(edge=lambda **kw: CookieJar())}):
            with self.assertRaises(RuntimeError):
                load_browser_cookies(make_session(), 'edge')
