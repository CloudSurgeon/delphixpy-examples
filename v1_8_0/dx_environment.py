#!/usr/bin/env python
#Corey Brune 08 2016
#This script creates an environment
#requirements
#pip install docopt delphixpy

#The below doc follows the POSIX compliant standards and allows us to use
#this doc to also define our arguments for the script.

"""Create Host Environment

Usage:
  dx_environment.py (--type <name> --env_name <name> --host_user <username> \
--ip <address> [--toolkit <path_to_the_toolkit>] [--ase --ase_user <name> --ase_pw <name>] \
|--update_ase_pw <name> --env_name <name> | --update_ase_user <name> --env_name <name> \
| --delete <env_name> | --refresh <env_name | --list)
[--logdir <directory>][--debug] [--config <filename>] [--connector_name <name>]
[--pw <password>][--engine <identifier>][--all] [--poll <n>]
   
  dx_environment.py -h | --help | -v | --version

Create a Delphix environment. (current support for standalone environments only)

Examples:
  dx_environment.py --engine landsharkengine --type linux --env_name test1 --host_user delphix --pw delphix --ip 182.1.1.1 --toolkit /var/opt/delphix
  dx_environment.py --type linux --env_name test1 --update_ase_pw newPasswd
  dx_environment.py --type linux --env_name test1 --host_user delphix --pw delphix --ip 182.1.1.1 --toolkit /var/opt/delphix
  dx_environment.py --type linux --env_name test1 --host_user delphix --pw delphix --ip 182.1.1.1 --toolkit /var/opt/delphix --ase --ase_user sa --ase_pw delphixpw
  dx_environment.py --type windows --env_name SOURCE --host_user delphix.local\\administrator --ip 10.0.1.50 --toolkit foo --config dxtools.conf --pw 'myTempPassword123!' --debug --connector_name 10.0.1.60
  dx_environment.py --list

Options:
  --type <name>             The OS type for the environment
  --env_name <name>         The name of the Delphix environment
  --ip <addr>               The IP address of the Delphix environment
  --list                    List all of the environments for a given engine
  --toolkit <path>          Path of the toolkit. Required for Unix/Linux
  --host_user <username>    The username on the Delphix environment
  --delete <environment>    The name of the Delphix environment to delete
  --update_ase_pw <name>    The new ASE DB password
  --refresh <environment>   The name of the Delphix environment to refresh
  --pw <password>           Password of the user
  --connector_name <environment>   The name of the Delphix connector to use. Required for Windows source environments
  --update_ase_user <name>  Update the ASE DB username
  --ase                     Flag to enable ASE environments
  --ase_user <name>         The ASE DB username
  --ase_pw <name>           Password of the ASE DB user
  --all                     Run against all engines.
  --debug                   Enable debug logging
  --parallel <n>            Limit number of jobs to maxjob
  --engine <type>           Identifier of Delphix engine in dxtools.conf.

  --poll <n>                The number of seconds to wait between job polls
                            [default: 10]
  --config <path_to_file>   The path to the dxtools.conf file
                            [default: ./dxtools.conf]
  --logdir <path_to_file>    The path to the logfile you want to use.
                            [default: ./dx_environment.log]
  -h --help                 Show this screen.
  -v --version              Show version.

"""

VERSION="v.0.3.604"

from docopt import docopt
from os.path import basename
import sys
import traceback
from time import sleep, time

from delphixpy.exceptions import HttpError
from delphixpy.exceptions import JobError
from delphixpy.exceptions import RequestError
from delphixpy.web import environment
from delphixpy.web import job
from delphixpy.web import host
from delphixpy.web.vo import UnixHostEnvironment
from delphixpy.web.vo import ASEHostEnvironmentParameters
from delphixpy.web.vo import HostEnvironmentCreateParameters
from delphixpy.web.vo import WindowsHostEnvironment

from lib.DlpxException import DlpxException
from lib.GetSession import GetSession
from lib.GetReferences import find_obj_by_name
from lib.GetReferences import find_obj_name
from lib.DxLogging import logging_est
from lib.DxLogging import print_info
from lib.DxLogging import print_debug
from lib.DxLogging import print_exception

def list_env():
    """
    List all environments for a given engine
    """

    all_envs = environment.get_all(dx_session_obj.server_session)
    for env in all_envs:
        env_user = find_obj_name(dx_session_obj.server_session,
                                 environment.user, env.primary_user)
        env_host = find_obj_name(dx_session_obj.server_session,
                                 host, env.host)

        #ORACLE CLUSTER does not have env.host
        #Windows does not have ASE instances

        print 'Environment Name: {}, Username: {}, Host: {}, Enabled: {}, ' \
              'ASE Environment Params: {}'.format(
            env.name, env_user, env_host, env.enabled,
            env.ase_host_environment_parameters if
            isinstance(env.ase_host_environment_parameters,
                       ASEHostEnvironmentParameters) else 'Undefined')


def delete_env(engine, env_name):
    """
    Deletes an environment

    engine: Dictionary of engines
    env_name: Name of the environment to delete
    """

    env_obj = find_obj_by_name(dx_session_obj.server_session, environment,
                                 env_name)

    if env_obj:
        environment.delete(dx_session_obj.server_session, env_obj.reference)
        dx_session_obj.jobs[engine['hostname']] = \
                                   dx_session_obj.server_session.last_job

    elif env_obj is None:
        print('Environment was not found in the Engine: {}'.format(env_name))
        sys.exit(1)


def refresh_env(engine, env_name):
    """
    Refresh the environment

    engine: Dictionary of engines
    env_name: Name of the environment to refresh
    """

    try:
        env_obj = find_obj_by_name(dx_session_obj.server_session, environment,
                                   env_name)
        environment.refresh(dx_session_obj.server_session, env_obj.reference)
        dx_session_obj.jobs[engine['hostname']] = \
                                   dx_session_obj.server_session.last_job

    except (DlpxException, RequestError) as e:
        print_exception('\nERROR: Refreshing the environment {} '
                        'encountered an error:\n{}'.format(env_name, e))
        sys.exit(1)


def update_ase_username():
    """
    Update the ASE database user password
    """

    env_obj = UnixHostEnvironment()
    env_obj.ase_host_environment_parameters = ASEHostEnvironmentParameters()
    env_obj.ase_host_environment_parameters.db_user = \
        arguments['--update_ase_user']

    try:
        environment.update(dx_session_obj.server_session, find_obj_by_name(
            dx_session_obj.server_session, environment, arguments['--env_name'],
            env_obj).reference, env_obj)

    except (HttpError, RequestError) as e:
        print_exception('\nERROR: Updating the ASE DB password '
                        'failed:\n{}\n'.format(e))


def update_ase_pw():
    """
    Update the ASE database user password
    """

    env_obj = UnixHostEnvironment()
    env_obj.ase_host_environment_parameters = ASEHostEnvironmentParameters()
    env_obj.ase_host_environment_parameters.credentials = {'type':
                                            'PasswordCredential',
                                                'password':
                                                arguments['--update_ase_pw']}

    try:
        environment.update(dx_session_obj.server_session, find_obj_by_name(
            dx_session_obj.server_session, environment, arguments['--env_name'],
            env_obj).reference, env_obj)

    except (HttpError, RequestError) as e:
        print_exception('\nERROR: Updating the ASE DB password '
                        'failed:\n{}\n'.format(e))


def create_linux_env(engine, env_name, host_user, ip_addr, toolkit_path,
                     pw=None):

    """
    Create a Linux environment.

    env_name: The name of the environment
    host_user: The server account used to authenticate 
    ip_addr: DNS name or IP address of the environment
    toolkit_path: Path to the toolkit. Note: This directory must be 
                  writable by the host_user
    pw: Password of the user. Default: None (use SSH keys instead)
    """

    env_params_obj = HostEnvironmentCreateParameters()

    if pw is None:
        print_debug('Creating the environment with SSH Keys',debug)
        env_params_obj.primary_user = {'type': 'EnvironmentUser',
                                          'name': host_user,
                                          'credential': {
                                          'type': 'SystemKeyCredential'}}

    else:
        print_debug('Creating the environment with a password',debug)
        env_params_obj.primary_user = {'type': 'EnvironmentUser',
                                          'name': host_user,
                                          'credential': {
                                          'type': 'PasswordCredential',
                                          'password': pw }}

    env_params_obj.host_parameters = {'type': 'UnixHostCreateParameters',
                                     'host': { 'address': ip_addr,
                                     'type': 'UnixHost',
                                     'name': env_name,
                                     'toolkitPath': toolkit_path}}

    env_params_obj.host_environment = UnixHostEnvironment()
    env_params_obj.host_environment.name = env_name

    if arguments['--ase']:
        env_params_obj.host_environment.ase_host_environment_parameters = \
            ASEHostEnvironmentParameters()

        try:
            env_params_obj.host_environment.ase_host_environment_parameters.db_user = \
                arguments['--ase_user']
            env_params_obj.host_environment.ase_host_environment_parameters.credentials = {
                                            'type': 'PasswordCredential',
                                            'password': arguments['--ase_pw']}
        except KeyError:
            print_exception('The --ase_user and --ase_pw arguments are'
                            ' required with the --ase flag.\n')

    try:
        environment.create(dx_session_obj.server_session,
                           env_params_obj)
        dx_session_obj.jobs[engine['hostname']] = \
                                   dx_session_obj.server_session.last_job

    except (DlpxException, RequestError, HttpError) as e:
        print('\nERROR: Encountered an exception while creating the '
              'environment:\n{}'.format(e))
    except JobError as e:
        print_exception('JobError while creating environment {}:\n{}'.format(
            e, e.message))


def create_windows_env(engine, env_name, host_user, ip_addr,
                     pw=None, connector_name=None):

    """
    Create a Windows environment.

    env_name: The name of the environment
    host_user: The server account used to authenticate 
    ip_addr: DNS name or IP address of the environment
    toolkit_path: Path to the toolkit. Note: This directory must be 
                  writable by the host_user
    pw: Password of the user. Default: None (use SSH keys instead)
    """

    env_params_obj = HostEnvironmentCreateParameters()

    print_debug('Creating the environment with a password',debug)

    env_params_obj.primary_user = {'type': 'EnvironmentUser',
                                      'name': host_user,
                                      'credential': {
                                      'type': 'PasswordCredential',
                                      'password': pw }}

    env_params_obj.host_parameters = {'type': 'WindowsHostCreateParameters',
                                     'host': { 'address': ip_addr,
                                     'type': 'WindowsHost',
                                     'name': env_name,
                                     'connectorPort': 9100}}

    env_params_obj.host_environment = WindowsHostEnvironment()
    env_params_obj.host_environment.name = env_name

    if connector_name:
      env_obj = find_obj_by_name(dx_session_obj.server_session, environment,
                                   connector_name)

      if env_obj:
        env_params_obj.host_environment.proxy = env_obj.host
      elif env_obj is None:
        print('Host was not found in the Engine: {}'.format(arguments[--connector_name]))
        sys.exit(1)

    try:
        environment.create(dx_session_obj.server_session,
                           env_params_obj)
        dx_session_obj.jobs[engine['hostname']] = \
                                   dx_session_obj.server_session.last_job

    except (DlpxException, RequestError, HttpError) as e:
        print('\nERROR: Encountered an exception while creating the '
              'environment:\n{}'.format(e))


def run_async(func):
    """
        http://code.activestate.com/recipes/576684-simple-threading-decorator/
        run_async(func)
            function decorator, intended to make "func" run in a separate
            thread (asynchronously).
            Returns the created Thread object

            E.g.:
            @run_async
            def task1():
                do_something

            @run_async
            def task2():
                do_something_too

            t1 = task1()
            t2 = task2()
            ...
            t1.join()
            t2.join()
    """
    from threading import Thread
    from functools import wraps

    @wraps(func)
    def async_func(*args, **kwargs):
        func_hl = Thread(target = func, args = args, kwargs = kwargs)
        func_hl.start()
        return func_hl

    return async_func


@run_async
def main_workflow(engine):
    """
    This function actually runs the jobs.
    Use the @run_async decorator to run this function asynchronously.
    This allows us to run against multiple Delphix Engine simultaneously

    """

    try:
       #Setup the connection to the Delphix Engine
       dx_session_obj.serversess(engine['ip_address'], engine['username'],
                                 engine['password'])

    except DlpxException as e:
        print_exception('\nERROR: Engine {} encountered an error while '
                        'provisioning {}:\n{}\n'.format(engine['hostname'],
                        arguments['--target'], e))
        sys.exit(1)

    thingstodo = ['thingtodo']

    try:
        with dx_session_obj.job_mode(single_thread):
            while (len(dx_session_obj.jobs) > 0 or len(thingstodo)> 0):
                if len(thingstodo)> 0:

                    if arguments['--type'] == 'linux' or arguments['--type'] == 'windows':
                        env_name = arguments['--env_name']
                        host_user = arguments['--host_user']
                        pw = arguments['--pw']
                        ip_addr = arguments['--ip']
                        host_name = arguments['--connector_name']
                        if arguments['--type'] == 'linux':
                          toolkit_path = arguments['--toolkit']
                          create_linux_env(engine, env_name, host_user,
                                        ip_addr, toolkit_path, pw)
                        else:
                          create_windows_env(engine, env_name, host_user,
                                        ip_addr, pw, host_name,)

                    elif arguments['--delete']:
                        delete_env(engine, arguments['--delete'])

                    elif arguments['--refresh']:
                        refresh_env(engine, arguments['--refresh'])

                    elif arguments['--update_ase_pw']:
                        update_ase_pw()

                    elif arguments['--update_ase_user']:
                        update_ase_username()
                    elif arguments['--list']:
                        list_env()

                    thingstodo.pop()

                #get all the jobs, then inspect them
                i = 0
                for j in dx_session_obj.jobs.keys():
                    job_obj = job.get(dx_session_obj.server_session,
                                      dx_session_obj.jobs[j])
                    print_debug(job_obj,debug)
                    print_info('{} Environment: {}'.format(
                               engine['hostname'], job_obj.job_state))

                    if job_obj.job_state in ["CANCELED", "COMPLETED", "FAILED"]:
                    #If the job is in a non-running state, remove it from the
                    # running jobs list.
                        del dx_session_obj.jobs[j]
                    else:
                        #If the job is in a running state, increment the
                        # running job count.
                        i += 1
                print_info('{}: {:d} jobs running.\n'.format(
                           engine['hostname'], i))

                #If we have running jobs, pause before repeating the checks.
                if len(dx_session_obj.jobs) > 0:
                    sleep(float(arguments['--poll']))

    except (DlpxException, JobError) as e:
        print_exception('\nError while creating the environment {}:'
                        '\n{}'.format(arguments['--env_name'], e.message))
        sys.exit(1)


def run_job():
    """
    This function runs the main_workflow aynchronously against all the 
    servers specified
    """
    engine = None

    #Create an empty list to store threads we create.
    threads = []

    #If the --all argument was given, run against every engine in dxtools.conf
    if arguments['--all']:
        print_info('Executing against all Delphix Engines in the dxtools.conf')

        try:
            #For each server in the dxtools.conf...
            for delphix_engine in dx_session_obj.dlpx_engines:
                engine = dx_session_obj[delphix_engine]
                #Create a new thread and add it to the list.
                threads.append(main_workflow(engine))

        except DlpxException as e:
            print_exception('Error encountered in run_job():\n{}'.format(e))
            sys.exit(1)

    elif arguments['--all'] is False:
        #Else if the --engine argument was given, test to see if the engine
        # exists in dxtools.conf
        if arguments['--engine']:
            try:
                engine = dx_session_obj.dlpx_engines[arguments['--engine']]
                print_info('Executing against Delphix Engine: {}\n'.format(
                           arguments['--engine']))

            except (DlpxException, KeyError) as e:
                print_exception('\nERROR: Delphix Engine {} cannot be '
                                    'found in {}. Please check your value '
                                    'and try again. Exiting.\n{}\n'.format(
                    arguments['--engine'], config_file_path, e))

        else:
            #Else search for a default engine in the dxtools.conf
            #import pdb;pdb.set_trace()
            for delphix_engine in dx_session_obj.dlpx_engines:
                if dx_session_obj.dlpx_engines[delphix_engine]['default'] == \
                        'true':

                    engine = dx_session_obj.dlpx_engines[delphix_engine]
                    print_info('Executing against the default Delphix Engine '
                               'in the dxtools.conf: {}'.format(
                           dx_session_obj.dlpx_engines[delphix_engine]['hostname']))

                break

            if engine is None:
                print_exception('\nERROR: No default engine found. Exiting')
                sys.exit(1)

        #run the job against the engine
        threads.append(main_workflow(engine))

    #For each thread in the list...
    for each in threads:
        #join them back together so that we wait for all threads to complete
        # before moving on
        each.join()


def time_elapsed():
    """
    This function calculates the time elapsed since the beginning of the script.
    Call this anywhere you want to note the progress in terms of time 
    """
    elapsed_minutes = round((time() - time_start)/60, +1)
    return elapsed_minutes


def main(argv):
    global single_thread
    global usebackup
    global time_start
    global config_file_path
    global dx_session_obj
    global debug

    try:
        dx_session_obj = GetSession()
        debug = arguments['--debug']
        logging_est(arguments['--logdir'], debug)
        print_debug(arguments, debug)
        time_start = time()
        single_thread = False
        config_file_path = arguments['--config']

        print_info('Welcome to %s version %s' % (basename(__file__),
                   VERSION))

        #Parse the dxtools.conf and put it into a dictionary
        dx_session_obj.get_config(config_file_path)


        #This is the function that will handle processing main_workflow for
        # all the servers.
        run_job()

        elapsed_minutes = time_elapsed()
        print_info('script took %s minutes to get this far. ' %
                   (str(elapsed_minutes)))

    #Here we handle what we do when the unexpected happens
    except SystemExit as e:
        """
        This is what we use to handle our sys.exit(#)
        """
        sys.exit(e)

    except DlpxException as e:
        """
        We use this exception handler when an error occurs in a function call.
        """

        print('\nERROR: Please check the ERROR message below:\n%s' %
              (e.message))
        sys.exit(2)

    except HttpError as e:
        """
        We use this exception handler when our connection to Delphix fails
        """
        print('\nERROR: Connection failed to the Delphix Engine. Please '
              'check the ERROR message below:\n%s' % (e.message))
        sys.exit(2)

    except JobError as e:
        """
        We use this exception handler when a job fails in Delphix so that we 
        have actionable data
        """
        print('A job failed in the Delphix Engine:\n%s' % (e.job))
        elapsed_minutes = time_elapsed()
        print_info(basename(__file__) + " took " + str(elapsed_minutes) +
                   " minutes to get this far.")
        sys.exit(3)

    except KeyboardInterrupt:
        """
        We use this exception handler to gracefully handle ctrl+c exits
        """
        print_debug("You sent a CTRL+C to interrupt the process",debug)
        elapsed_minutes = time_elapsed()
        print_info(basename(__file__) + " took " + str(elapsed_minutes) +
                   " minutes to get this far.")

    except:
        """
        Everything else gets caught here
        """
        print(sys.exc_info()[0])
        print(traceback.format_exc())
        elapsed_minutes = time_elapsed()
        print_info('%s took %s minutes to get this far' % (basename(__file__),
                   str(elapsed_minutes)))
        sys.exit(1)


if __name__ == "__main__":
    #Grab our arguments from the doc at the top of the script
    arguments = docopt(__doc__, version=basename(__file__) + " " + VERSION)
    #Feed our arguments to the main function, and off we go!
    main(arguments)
