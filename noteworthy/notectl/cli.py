import argparse
import sys


from noteworthy.notectl import NoteworthyController


class NoteworthyCLI:
    def __init__(self, arg_parser):
        self.controller = NoteworthyController()
        self.arg_parser = arg_parser
        self.setup_argparse()

    def dispatch(self):
        '''Translate cli arguments into method invocations passing everything
        we get from argparse as kwargs.
        '''
        # use root arg_parser here
        args = self.args
        if args.command in self.controller.plugins:
            plugin = args.command
            command = args.action
            if not command:
                command = 'help'
            # instantiate the plugin
            plugin = self.controller.plugins[plugin].Controller()
            # use plugin arg parser to parse args
            plugin_args = plugin.sub_parser.parse_known_args(sys.argv[3:])[0]
            if self.args.debug:
                print(plugin_args)
            NoteworthyCLI._invoke_method(plugin, command, plugin_args.__dict__)
            sys.exit(0)
        NoteworthyCLI._invoke_method(self.controller, args.command, args.__dict__)

    def setup_argparse(self):
        self.controller.setup_argparse(self.arg_parser)
        for plugin, module in self.controller.plugins.items():
            module.Controller.setup_argparse(self.arg_parser)
        self.args = self.arg_parser.parse_known_args()[0]
        if self.args.debug:
            print(self.args)

    @staticmethod
    def _invoke_method(target, method, kwargs):
        method = getattr(target, method)
        method(**kwargs)