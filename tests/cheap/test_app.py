import unittest
from heymans.server import create_app, HeymansConfig
from heymans import config


class UnitTestConfig(HeymansConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    

class BaseRoutesTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(config_class=UnitTestConfig)
        self.client = self.app.test_client(use_cookies=True)
        self.app_context = self.app.app_context()
        self.app_context.push()
        
    def tearDown(self):
        self.app_context.pop()
