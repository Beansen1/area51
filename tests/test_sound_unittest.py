import os
import wave
import tempfile
import unittest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sound as sfx


class SoundTests(unittest.TestCase):
    def test_best_key_for_filename(self):
        self.assertEqual(sfx._best_key_for_filename('click.wav'), 'click')
        self.assertEqual(sfx._best_key_for_filename('Correct_or_Payment.wav'), 'success')
        self.assertEqual(sfx._best_key_for_filename('WRONG_fail.wav'), 'error')

    def test_get_duration_reads_wav(self):
        tmpdir = tempfile.mkdtemp()
        p = os.path.join(tmpdir, 't.wav')
        fr = 8000
        n = fr * 1
        with wave.open(p, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(fr)
            wf.writeframes(b'\x00\x00' * n)

        sfx._sound_paths['t'] = p
        d = sfx.get_duration('t')
        self.assertAlmostEqual(d, 1.0, places=2)


if __name__ == '__main__':
    unittest.main()
