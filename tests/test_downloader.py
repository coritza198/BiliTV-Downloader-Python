import unittest
from bilitv_downloader import parse_link, check_media_url, subtitle_candidates, safe_lang

class DownloaderTests(unittest.TestCase):
    def test_video(self):
        self.assertEqual(parse_link('https://www.bilibili.tv/video/123')['aid'], '123')
    def test_episode(self):
        self.assertEqual(parse_link('https://www.bilibili.tv/play/1/22')['ep_id'], '22')
    def test_host_rejected(self):
        for url in ('http://www.bilibili.tv/video/1', 'https://evil.com/video/1', 'https://www.bilibili.tv.evil.com/video/1'):
            with self.assertRaises(ValueError): parse_link(url)
    def test_media_url(self):
        with self.assertRaises(ValueError): check_media_url('http://localhost/test')
    def test_subtitles(self):
        self.assertEqual(subtitle_candidates({'subtitle': [{'lang':'en','url':'https://cdn.example/sub.vtt'}]}), [('en','https://cdn.example/sub.vtt')])
    def test_safe_lang(self):
        self.assertEqual(safe_lang('../../en'), '______en')

if __name__ == '__main__': unittest.main()
