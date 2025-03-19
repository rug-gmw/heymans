import unittest
from http import HTTPStatus
from heymans.server import create_app, HeymansConfig
from heymans import config
from redis import Redis


class UnitTestConfig(HeymansConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    

class BaseRoutesTestCase(unittest.TestCase):

    def setUp(self):
        Redis().flushdb()
        self.app = create_app(config_class=UnitTestConfig)
        self.client = self.app.test_client(use_cookies=True)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.login()
        
    def login(self):
        response = self.client.post('/app/login', data=dict(
            username='1',
            password='dummy'
        ), follow_redirects=True)
        assert response.status_code == 200        
        
    def tearDown(self):
        self.app_context.pop()

    @staticmethod
    def compare_dicts_ignore_none(dict1, dict2):
        """Recursively compare two dicts, ignoring keys with None values."""
        for key in set(dict1) | set(dict2):
            if key.endswith('_id'):
                continue
            if isinstance(dict1, (str, bytes, int, float)) and \
                    isinstance(dict2, (str, bytes, int, float)):
                return dict1 == dict2
            val1 = dict1.get(key, None)
            val2 = dict2.get(key, None)
            if isinstance(val1, dict) and isinstance(val2, dict):
                if not BaseRoutesTestCase.compare_dicts_ignore_none(val1,
                                                                    val2):
                    return False
            if isinstance(val1, list) and isinstance(val2, list):
                for v1, v2 in zip(val1, val2):
                    if not BaseRoutesTestCase.compare_dicts_ignore_none(v1,
                                                                        v2):
                        return False
            elif val1 != val2 and not (val1 is None or val2 is None):
                breakpoint()
                return False
        return True
