from noteworthy.notectl.plugins import NoteworthyPlugin


class AuthController(NoteworthyPlugin):

    PLUGIN_NAME = 'auth'

    def __init__(self):
        pass


Controller = AuthController
