import unittest
from bilitv_gui import parse_jobs, validate_name, numbered_name

class GuiTests(unittest.TestCase):
    def test_jobs(self):
        jobs = parse_jobs('https://www.bilibili.tv/video/123 | Tap 01\nhttps://www.bilibili.tv/video/456')
        self.assertEqual(jobs[0][1], 'Tap 01')
        self.assertIsNone(jobs[1][1])
    def test_invalid_names(self):
        for name in ('../abc', 'CON', 'hello?', 'x\\y', ''):
            with self.assertRaises(ValueError):
                validate_name(name)
    def test_numbering(self):
        self.assertEqual([numbered_name('tập_', '22', i) for i in range(1, 4)], ['tập_22', 'tập_23', 'tập_24'])
        self.assertEqual(numbered_name('Anime_', '0022', 2), 'Anime_0023')
        with self.assertRaises(ValueError):
            numbered_name('tập_', '-1', 1)

    def test_duplicate(self):
        with self.assertRaises(ValueError):
            parse_jobs('https://www.bilibili.tv/video/123 | A\nhttps://www.bilibili.tv/video/456 | a')

if __name__ == '__main__':
    unittest.main()
