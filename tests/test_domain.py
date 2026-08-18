from hashlib import sha256
import unittest

from remarkable_publish.domain import publish_key


class DomainTests(unittest.TestCase):
    def test_publish_key_covers_rendered_pdf_intent(self) -> None:
        digest = sha256(b"pdf").hexdigest()
        first = publish_key("Brief", digest)
        self.assertEqual(first, publish_key(" Brief ", digest))
        self.assertNotEqual(first, publish_key("Other", digest))


if __name__ == "__main__":
    unittest.main()
