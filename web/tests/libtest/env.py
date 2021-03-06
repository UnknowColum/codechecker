# -----------------------------------------------------------------------------
#                     The CodeChecker Infrastructure
#   This file is distributed under the University of Illinois Open Source
#   License. See LICENSE.TXT for details.
# -----------------------------------------------------------------------------
"""
Test environment setup and configuration helpers.
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import division

from hashlib import sha256
import os
import json
import tempfile
import shutil
import socket
import stat
import subprocess
import sys

from .thrift_client_to_db import get_auth_client
from .thrift_client_to_db import get_config_client
from .thrift_client_to_db import get_product_client
from .thrift_client_to_db import get_viewer_client

from functional import PKG_ROOT
from functional import REPO_ROOT

from libcodechecker import util


def get_free_port():
    """
    Get a free port from the OS.
    """
    # TODO: Prone to errors if the OS assigns port to someone else before use.

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    free_port = s.getsockname()[1]
    s.close()

    return free_port


def get_postgresql_cfg():
    """
    Returns PostgreSQL config if should be used based on the environment
    settings if not return none.
    """
    use_postgresql = os.environ.get('TEST_USE_POSTGRESQL', '') == 'true'
    if use_postgresql:
        pg_db_config = {'dbaddress': 'localhost',
                        'dbport': os.environ.get('TEST_DBPORT'),
                        'dbname': 'codechecker_config_' +
                                  os.environ['CODECHECKER_DB_DRIVER']
                        }
        if os.environ.get('TEST_DBUSERNAME', False):
            pg_db_config['dbusername'] = os.environ['TEST_DBUSERNAME']
        return pg_db_config
    else:
        return None


def add_database(dbname, env=None):
    """
    Creates a new database with a given name.
    This has no effect outside PostgreSQL mode. (SQLite databases are
    created automatically by Python.)
    """

    pg_config = get_postgresql_cfg()
    if pg_config:
        pg_config['dbname'] = dbname

        psql_command = ['psql',
                        '-h', pg_config['dbaddress'],
                        '-p', str(pg_config['dbport']),
                        '-d', 'postgres',
                        '-c', "CREATE DATABASE \"" + pg_config['dbname'] + "\""
                        ]
        if 'dbusername' in pg_config:
            psql_command += ['-U', pg_config['dbusername']]

        print(psql_command)
        subprocess.call(psql_command, env=env)


def del_database(dbname, env=None):
    """
    Deletes the given database.
    This has no effect outside PostgreSQL mode.
    """

    pg_config = get_postgresql_cfg()
    if pg_config:
        pg_config['dbname'] = dbname

        remove_cmd = """
            UPDATE pg_database
            SET datallowconn='false'
            WHERE datname='{0}';

            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname='{0}';

            DROP DATABASE "{0}";
        """.format(dbname)

        with tempfile.NamedTemporaryFile(suffix='.sql') as sql_file:
            sql_file.write(remove_cmd)
            sql_file.flush()

            psql_command = ['psql',
                            '-h', pg_config['dbaddress'],
                            '-p', str(pg_config['dbport']),
                            '-d', 'postgres',
                            '-f', sql_file.name]

            if 'dbusername' in pg_config:
                psql_command += ['-U', pg_config['dbusername']]

            print(' '.join(psql_command))
            subprocess.call(psql_command,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            env=env)


def clang_to_test():
    return "clang_"+os.environ.get('TEST_CLANG_VERSION', 'stable')


def setup_viewer_client(workspace,
                        endpoint='/CodeCheckerService',
                        auto_handle_connection=True,
                        session_token=None, proto='http'):
    # Read port and host from the test config file.
    codechecker_cfg = import_test_cfg(workspace)['codechecker_cfg']
    port = codechecker_cfg['viewer_port']
    host = codechecker_cfg['viewer_host']
    product = codechecker_cfg['viewer_product']

    if session_token is None:
        session_token = get_session_token(workspace)

    if session_token == '_PROHIBIT':
        session_token = None

    return get_viewer_client(host=host,
                             port=port,
                             product=product,
                             endpoint=endpoint,
                             auto_handle_connection=auto_handle_connection,
                             session_token=session_token,
                             protocol=proto)


def setup_auth_client(workspace,
                      uri='/Authentication',
                      auto_handle_connection=True,
                      session_token=None, proto='http'):

    codechecker_cfg = import_test_cfg(workspace)['codechecker_cfg']
    port = codechecker_cfg['viewer_port']
    host = codechecker_cfg['viewer_host']

    if session_token is None:
        session_token = get_session_token(workspace)

    if session_token == '_PROHIBIT':
        session_token = None

    return get_auth_client(port=port,
                           host=host,
                           uri=uri,
                           auto_handle_connection=auto_handle_connection,
                           session_token=session_token, protocol=proto)


def setup_product_client(workspace,
                         product=None,
                         uri='/Products',
                         auto_handle_connection=True,
                         session_token=None, proto='http'):

    codechecker_cfg = import_test_cfg(workspace)['codechecker_cfg']
    port = codechecker_cfg['viewer_port']
    host = codechecker_cfg['viewer_host']

    if session_token is None:
        session_token = get_session_token(workspace)

    if session_token == '_PROHIBIT':
        session_token = None

    return get_product_client(port=port,
                              host=host,
                              product=product,
                              uri=uri,
                              auto_handle_connection=auto_handle_connection,
                              session_token=session_token, protocol=proto)


def setup_config_client(workspace,
                        uri='/Configuration',
                        auto_handle_connection=True,
                        session_token=None, proto='http'):

    codechecker_cfg = import_test_cfg(workspace)['codechecker_cfg']
    port = codechecker_cfg['viewer_port']
    host = codechecker_cfg['viewer_host']

    if session_token is None:
        session_token = get_session_token(workspace)

    if session_token == '_PROHIBIT':
        session_token = None

    return get_config_client(port=port,
                             host=host,
                             uri=uri,
                             auto_handle_connection=auto_handle_connection,
                             session_token=session_token, protocol=proto)


def repository_root():
    return os.path.abspath(os.environ['REPO_ROOT'])


def test_proj_root():
    return os.path.abspath(os.environ['TEST_PROJ'])


def setup_test_proj_cfg(workspace):
    return import_test_cfg(workspace)['test_project']


def import_codechecker_cfg(workspace):
    return import_test_cfg(workspace)['codechecker_cfg']


def get_run_names(workspace):
    return import_test_cfg(workspace)['codechecker_cfg']['run_names']


def parts_to_url(codechecker_cfg):
    """
    Creates a product URL string from the test configuration dict.
    """
    return codechecker_cfg['viewer_host'] + ':' + \
        str(codechecker_cfg['viewer_port']) + '/' + \
        codechecker_cfg['viewer_product']


def get_workspace(test_id='test'):
    tmp_dir = os.path.join(REPO_ROOT, 'build')
    base_dir = os.path.join(tmp_dir, 'workspace')
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    if test_id:
        return tempfile.mkdtemp(prefix=test_id+"-", dir=base_dir)
    else:
        return base_dir


def clean_wp(workspace):
    if os.path.exists(workspace):
        print("Removing workspace:" + workspace)
        shutil.rmtree(workspace)
    os.makedirs(workspace)


def import_test_cfg(workspace):
    cfg_file = os.path.join(workspace, "test_config.json")
    test_cfg = {}
    with open(cfg_file, 'r') as cfg:
        test_cfg = json.loads(cfg.read())
    return test_cfg


def export_test_cfg(workspace, test_cfg):
    cfg_file = os.path.join(workspace, "test_config.json")
    with open(cfg_file, 'w') as cfg:
        cfg.write(json.dumps(test_cfg, sort_keys=True, indent=2))


def codechecker_cmd():
    return os.path.join(PKG_ROOT, 'bin', 'CodeChecker')


def codechecker_package():
    return PKG_ROOT


def codechecker_env():
    checker_env = os.environ.copy()
    cc_bin = os.path.join(codechecker_package(), 'bin')
    checker_env['PATH'] = cc_bin + ":" + checker_env['PATH']
    return checker_env


def test_env(test_workspace):
    base_env = os.environ.copy()
    base_env['PATH'] = os.path.join(codechecker_package(), 'bin') + \
        ':' + base_env['PATH']
    base_env['HOME'] = test_workspace
    return base_env


def enable_auth(workspace):
    """
    Create a dummy authentication-enabled configuration and
    an auth-enabled server.

    Running the tests only work if the initial value (in package
    server_config.json) is FALSE for authentication.enabled.
    """

    server_config_filename = "server_config.json"

    cc_package = codechecker_package()
    original_auth_cfg = os.path.join(cc_package,
                                     'config',
                                     server_config_filename)

    shutil.copy(original_auth_cfg, workspace)

    server_cfg_file = os.path.join(workspace,
                                   server_config_filename)

    scfg_dict = util.load_json_or_empty(server_cfg_file, {})
    scfg_dict["authentication"]["enabled"] = True
    scfg_dict["authentication"]["method_dictionary"]["enabled"] = True
    scfg_dict["authentication"]["method_dictionary"]["auths"] = \
        ["cc:test", "john:doe", "admin:admin123"]

    with open(server_cfg_file, 'w') as scfg:
        json.dump(scfg_dict, scfg, indent=2, sort_keys=True)

    # Create a root user.
    root_file = os.path.join(workspace, 'root.user')
    with open(root_file, 'w') as rootf:
        rootf.write(sha256("root:root").hexdigest())
    os.chmod(root_file, stat.S_IRUSR | stat.S_IWUSR)


def enable_storage_of_analysis_statistics(workspace):
    """
    Enables storing analysis statistics information for the server.
    """

    server_config_filename = "server_config.json"

    cc_package = codechecker_package()
    original_auth_cfg = os.path.join(cc_package,
                                     'config',
                                     server_config_filename)

    shutil.copy(original_auth_cfg, workspace)

    server_cfg_file = os.path.join(workspace,
                                   server_config_filename)

    scfg_dict = util.load_json_or_empty(server_cfg_file, {})
    scfg_dict["store"]["analysis_statistics_dir"] = \
        os.path.join(workspace, 'analysis_statistics')

    with open(server_cfg_file, 'w') as scfg:
        json.dump(scfg_dict, scfg, indent=2, sort_keys=True)


def enable_ssl(workspace):
    """
    Create a dummy ssl-enabled server config.
    """

    repo_root = repository_root()
    ssl_cert = os.path.join(repo_root,
                            'tests',
                            'ssl_example_cert',
                            'cert.pem')
    ssl_key = os.path.join(repo_root,
                           'tests',
                           'ssl_example_cert',
                           'key.pem')

    shutil.copy(ssl_cert, workspace)
    shutil.copy(ssl_key, workspace)
    print("copied "+ssl_cert+" to "+workspace)


def get_session_token(test_folder):
    """
    Retrieve the session token for the server in the test workspace.
    This function assumes that only one entry exists in the session file.
    """

    try:
        server_data = import_test_cfg(test_folder)['codechecker_cfg']
        session_file = os.path.join(test_folder, '.codechecker.session.json')
        with open(session_file, 'r') as sess_file:
            sess_dict = json.load(sess_file)

        host_port_key = server_data['viewer_host'] + ':' + \
            str(server_data['viewer_port'])
        return sess_dict['tokens'][host_port_key]
    except (IOError, KeyError) as err:
        print("Could not load session for session getter because " +
              err.message)
        return None
