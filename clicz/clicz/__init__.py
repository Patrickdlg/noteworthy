#!/usr/bin/env python
import argparse
import sys
import functools
import inspect
import yaml
import pkg_resources


COLORS = {
        'HEADER' : '\033[95m',
        'BLUE' : '\033[94m',
        'GREEN' : '\033[92m',
        'YELLOW' : '\033[93m',
        'RED' : '\033[91m',
        'ENDC' : '\033[0m',
        'BOLD' : '\033[1m',
        'UNDERLINE' : '\033[4m'
}

class Color:
    def __getattr__(self, color: str):
        color = color.upper()
        def colorize(message: str):
            return f"{COLORS[color]}{message}{COLORS['ENDC']}"
        return colorize

class CLICZ:


    def __init__(self):
        '''
        Register any controller that has the property `enable_cli=True`
        '''
        self.color = Color()
        self.registered_controllers = {}
        self.controller_instances = {}
        self.proxy_commands = {}
        epilog = 'Run `notectl <command> --help` for more information.'
        self.parser = argparse.ArgumentParser(epilog=epilog)
        self.parser_subparser_factory = self.parser.add_subparsers(title='Management commands', dest='mgmt_command', metavar='')
        self.base_parser = argparse.ArgumentParser(epilog=epilog)
        self.base_parser.add_argument('-d', '--debug', help='show debug output', action='store_true')
        self.base_parser._action_groups.append(self.parser._action_groups[-1])
        self.sub_parser_factory = self.base_parser.add_subparsers(title='Plugin commands', dest='command', required=True, metavar='')
        description = self._init_clicz()
        self.parser.description = description
        self.base_parser.description = description

    def _init_clicz(self) -> str:
        '''Initialize clicz application
        ---
        Args: None
        Returns: Argparser description
        '''
        entrypoint = list(pkg_resources.iter_entry_points('clicz.entrypoint'))[0]
        clicz_module = entrypoint.load()
        return clicz_module.clicz_entrypoint(self)

    def dispatch(self, argv=None):
        '''Dispatch a CLI invocation to a controller.
        First, we fetch the controller class from the map of registered controllers (methods wrapped wit @cli_method)
        then we construct an ArgParser based on the Docstring
        '''

        try:
            if sys.argv[1] in self.proxy_commands:
                self.parser.parse_known_args()
                alias_key = sys.argv[1]
                sys.argv.insert(1, self.proxy_commands[alias_key][0])
                sys.argv.insert(2, self.proxy_commands[alias_key][1])
                sys.argv.remove(alias_key)
        except IndexError:
            sys.argv.insert(1, '--help')
        if not argv:
            argv = sys.argv
        args = self.base_parser.parse_args()
        controller_name = args.command
        controller_method = args.subcommand
        if controller_name not in self.registered_controllers:
            raise Exception(f'Subcommand {controller_name} not found')
        controller = self.registered_controllers[controller_name]
        controller_instance = controller()
        self.controller_instances[controller_name] = controller_instance
        if not hasattr(controller_instance, controller_method):
            raise Exception(f'Controller {controller_name} has no CLI method {controller_method}')
        method = getattr(controller_instance, controller_method)
        if not hasattr(method, 'cli_method'):
            raise Exception(f'Method {method.__qualname__} not registered for CLI invocation.'
                             ' Wrap method with @cli_method to expose via CLI.')
        return method(*method.get_invocation_args(args))

    def register_controller(self, controller):
        self.registered_controllers[controller.PLUGIN_NAME] = controller
        self.parsers = {}
        self.parsers[controller.PLUGIN_NAME] = self.sub_parser_factory.add_parser(controller.PLUGIN_NAME, help=inspect.getdoc(controller))
        controller_sub_parser_factory = self.parsers[controller.PLUGIN_NAME].add_subparsers(title='commands', dest='subcommand', required=True, metavar='')
        for method_name, method in vars(controller).items():
            if hasattr(method, 'cli_method'):
                self._build_method_argparser(controller_sub_parser_factory, controller.PLUGIN_NAME, method_name, method)

    def _register_proxy_commands(self, aliases, controller_name, method_name):
        for alias in aliases:
            if alias in self.proxy_commands:
                raise Exception(f'{alias} already registered. Cannot top-level alias with same name.')
            self.proxy_commands[alias] = (controller_name, method_name)

    def _build_method_argparser(self, sub_parser_factory, controller_name, method_name, method):
        '''
        '''
        method_description = inspect.getdoc(method)
        if not method_description:
            raise Exception(f'Missing docstring for {self.color.red(method.__qualname__)}. Docstrings are required.')
        try:
            method_description = inspect.getdoc(method).split('---', 1)[0]
        except KeyError:
            pass
        alias_parser = None
        if hasattr(method, 'clicz_aliases'):
            self._register_proxy_commands(method.clicz_aliases, controller_name, method_name)
            alias_parser = self.parser_subparser_factory.add_parser(method.clicz_aliases[0], help=method_description, description=method_description, aliases=method.clicz_aliases[1:])
            method_arg_parser = sub_parser_factory.add_parser(method_name, help=method_description, description=method_description, aliases=method.clicz_aliases)
        else:
            method_arg_parser = sub_parser_factory.add_parser(method_name, help=method_description, description=method_description)

        argspec = inspect.getfullargspec(method.__wrapped__)
        static_method = False
        if argspec.args[0] not in ['cls', 'self']:
            static_method = True
        start_arg_idx = 0 if static_method else 1
        docstring = inspect.getdoc(method)
        if not docstring:
            raise Exception('YAML based Docstring are required for clicz methods.')
        else:
            # Parse YAML based docstring to auto-generate ArgParser with nice help!
            # if method is static and has arguments or not a static_method with more than 1 args
            if (static_method and len(argspec.args)) or (not static_method and len(argspec.args) > 1):
                docstring = docstring.split('---', 1)[1]
                argspec.args.reverse()
                defaults = dict(zip(argspec.args, argspec.defaults)) if argspec.defaults else []
                try:
                    doc_yaml = yaml.safe_load(docstring)
                except:
                    raise Exception('Unable to parse docstring; not valid YAML.')
                if not isinstance(doc_yaml, dict) or 'args' not in [key.lower() for key in [*doc_yaml.keys()]]:
                    raise Exception('Docstring YAML missing Args key.')
                for arg, help in doc_yaml['Args'].items():
                    if not isinstance(help, str):
                        raise Exception(f'Argument description for {arg} must be of type str.')
                    if arg in defaults:
                        method_arg_parser.add_argument(f'--{arg}', default=defaults[arg], help=help)
                        if alias_parser:
                            alias_parser.add_argument(f'--{arg}', default=defaults[arg], help=help)

                    else:
                        method_arg_parser.add_argument(f'{arg}', help=help)
                        if alias_parser:
                            alias_parser.add_argument(f'{arg}', help=help)
                argspec.args.reverse()
                # make sure docstring YAML spe  cifies all arguments defined in argspec
                missing_args = list(set(argspec.args).difference(set([*doc_yaml['Args'].keys()])))
                [missing_args.remove(x) for x in ['self', 'cls'] if x in missing_args]
                if missing_args:
                    raise Exception(f"Docstring for {self.color.red(method.__qualname__)} missing args: {', '.join(missing_args)}")
            def get_invocation_args(parsed_args):
                return [ getattr(parsed_args, key) for key in argspec.args[start_arg_idx:] ]
            method.get_invocation_args = get_invocation_args

def cli_method(func=None, parse_docstring=True):
    if not func:
        return functools.partial(cli_method, parse_docstring=parse_docstring)
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        return res
    wrapper.parse_docstring = True if parse_docstring else False
    wrapper.cli_method = True
    return wrapper