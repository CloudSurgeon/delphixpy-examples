"""
Module that provides lookups of references and names of Delphix objects.
"""

import re
from datetime import datetime
from dateutil import tz

from delphixpy.web.service import time
from delphixpy.exceptions import RequestError
from delphixpy.exceptions import HttpError
from delphixpy.exceptions import JobError
from delphixpy.web import repository
from delphixpy.web import database
from delphixpy.web import sourceconfig

from DlpxException import DlpxException
from DxLogging import print_debug
from DxLogging import print_exception

VERSION = 'v.0.2.0013'

def convert_timestamp(engine, timestamp):
    """
    Convert timezone from Zulu/UTC to the Engine's timezone

    engine: A Delphix engine session object.
    timestamp: the timstamp in Zulu/UTC to be converted
    """

    default_tz = tz.gettz('UTC')
    engine_tz = time.time.get(engine)

    try:
        convert_tz = tz.gettz(engine_tz.system_time_zone)
        utc = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S')
        utc = utc.replace(tzinfo=default_tz)
        converted_tz = utc.astimezone(convert_tz)
        engine_local_tz = '{} {} {}'.format(str(converted_tz.date()),
                                            str(converted_tz.time()),
                                            str(converted_tz.tzname()))

        return engine_local_tz
    except TypeError:
        return None


def find_all_objects(engine, f_class):
    """
    Return all objects from a given class

    engine: A Delphix engine session object
    f_class: The objects class. I.E. database or timeflow.
    :return: List of objects
    """

    return_lst = []

    try:
        return f_class.get_all(engine)

    except (JobError, HttpError) as e:
        raise DlpxException('{} Error encountered in {}: {}\n'.format(
            engine.address, f_class, e))


def find_obj_specs(engine, obj_lst):
    """
    Function to find objects for replication
    :param engine: Delphix Virtualization session object
    :param obj_lst: List of names for replication
    :return: List of references for the given object names
    """
    rep_lst = []
    for obj in obj_lst:
        rep_lst.append(find_obj_by_name(engine, database, obj).reference)
    return rep_lst


def find_obj_list(obj_lst, obj_name):
    """
    Function to find an object in a list of objects
    obj_lst: List containing objects from the get_all() method
    obj_name: Name of the object to match
    :return: The named object. None is returned if no match is found.`
    """
    for obj in obj_lst:
        if obj_name == obj.name:
            return obj
    return None


def find_obj_by_name(engine, f_class, obj_name, active_branch=False):
    """
    Function to find objects by name and object class, and return object's 
    reference as a string

    engine: A Delphix engine session object
    f_class: The objects class. I.E. database or timeflow.
    obj_name: The name of the object
    active_branch: Default = False. If true, return list containing
                   the object's reference and active_branch. Otherwise, return 
                   the reference.
    """

    return_list = []

    try:
        all_objs = f_class.get_all(engine)
    except AttributeError as e:
        raise DlpxException('Could not find reference for object class'
                            '{}.\n'.format(e))
    for obj in all_objs:
        if obj.name == obj_name:

            if active_branch is False:
                return(obj)

            #This code is for JS objects only.
            elif active_branch is True:
                return_list.append(obj.reference)
                return_list.append(obj.active_branch)
                return(return_list)

            return obj

    #If the object isn't found, raise an exception.
    raise DlpxException('{} was not found on engine {}.\n'.format(
        obj_name, engine.address))


def get_obj_reference(engine, obj_type, obj_name, search_str=None,
                      container=False):
    """
    Return the reference for the provided object name

    engine: A Delphix engine object.
    results: List containing object name
    search_str (optional): string to search within results list
    container (optional): search for container instead of name
    """

    ret_lst = []

    results = obj_type.get_all(engine)

    for result in results:
        if container is False:
            if result.name == obj_name:
                ret_lst.append(result.reference)

                if search_str:
                    if re.search(search_str, result.reference, re.IGNORECASE):
                        ret_lst.append(True)
                    else:
                        ret_lst.append(False)

                return ret_lst
        else:
            if result.container == obj_name:
                ret_lst.append(result.reference)

                return ret_lst

    raise DlpxException('Reference not found for {}'.format(obj_name))


def get_db_name(engine, db_reference):
    """
    Return the database name from db_reference

    engine: A Delphix engine object.
    db_reference: The datbase reference to retrieve the db_name
    """

    try:
        db_name = database.get(engine, db_reference)
        return db_name.name

    except RequestError as e:
        raise DlpxException(e)

    except (JobError, HttpError) as e:
        raise DlpxException(e.message)


def find_dbrepo(engine, install_type, f_environment_ref, f_install_path):
    """
    Function to find database repository objects by environment reference and
    install path, and return the object's reference as a string
    You might use this function to find Oracle and PostGreSQL database repos.

    engine: Virtualization Engine Session object
    install_type: Type of install - Oracle, ASE, SQL
    f_environment_ref: Reference of the environment for the repository
    f_install_path: Path to the installation directory.

    return: delphixpy.web.vo.SourceRepository object
    """

    print_debug('Searching objects in the %s class for one with the '
                'environment reference of %s and an install path of %s' %
                (install_type, f_environment_ref, f_install_path))
    #import pdb;pdb.set_trace()
    all_objs = repository.get_all(engine, environment=f_environment_ref)
    for obj in all_objs:
        if 'OracleInstall' == install_type:
            if (obj.type == install_type and
                obj.installation_home == f_install_path):

                print_debug('Found a match %s'.format(obj.reference))
                return obj

        elif 'MSSqlInstance' == install_type:
            if (obj.type == install_type and
                obj.instance_name == f_install_path):

                print_debug('Found a match {}'.format(obj.reference))
                return obj

        else:
            raise DlpxException('No Repo match found for type {}.\n'.format(
                install_type))

def find_sourceconfig(engine, sourceconfig_name, f_environment_ref):
    """
    Function to find database sourceconfig objects by environment reference and
    sourceconfig name (db name), and return the object's reference as a string
    You might use this function to find Oracle and PostGreSQL database sourceconfigs.

    engine: Virtualization Engine Session object
    sourceconfig_name: Name of source config, usually name of db instnace (ie. orcl)
    f_environment_ref: Reference of the environment for the repository

    return: delphixpy.web.vo.SourceConfig object
    """

    print_debug('Searching objects in the SourceConfig class for one with the '
                'environment reference of %s and a name of %s' %
                (f_environment_ref, sourceconfig_name))
    all_objs = sourceconfig.get_all(engine, environment=f_environment_ref)
    for obj in all_objs:
        if obj.name == sourceconfig_name:
                print_debug('Found a match %s'.format(obj.reference))
                return obj
        else:
            raise DlpxException('No sourceconfig match found for type {}.\n'.format(
                sourceconfig_name))