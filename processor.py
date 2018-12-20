"""Queries for and restores xmatters instance data

.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html

"""

from io import TextIOBase
import json
import pprint
import sys
import time
import urllib.parse


import requests
from requests.auth import HTTPBasicAuth
from requests import Session
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter, column_index_from_string

import config
import common_logger

_logger = None
_users = None
_site_dict = {}
_user_dict = {}
_supervisor_dict = {}
_group_dict = {}


def _log_xm_error(url, response):
    """Captures and logs errors
        
    Logs the error caused by attempting to call url.
        
    Args:
        url (str): The location being requested that caused the error
        response (object): JSON object that holds the error response
    """
    body = response.json()
    if response.status_code == 404:
        _logger.warn(config.ERR_INITIAL_REQUEST_FAILED_MSG,
                     response.status_code, url)
    else:
        _logger.error(f'Response - ' \
                      f'code: {body["code"] if "code" in body else "none"}, ' \
                      f'reason: {body["reason"] if "reason" in body else "none"}, ' \
                      f'message: {body["message"] if "message" in body else "none"}, ' \
                      f'\n\tURL: {url}')

def _open_in_file(filename: str) -> TextIOBase:
    """Opens data file to restore
    
    Args:
        filename (str): Name of file to read from

    Returns:
        file: inFile
    """
    inFile = open(filename)
    return inFile

def _add_site(site_json):
    """Attempst to add a new Site object from the JSON string.
        
    Creates a dict object to pass to xMatters to create a new Site
        
    Args:
        site_json: The JSON payload representing the Site to add
    """
    # Conver the Site JSON string to an object
    site_obj = json.loads(site_json)
    
    # Set our resource URLs
    url = config.xmod_url + '/api/xm/1/sites'
    _logger.debug('Attempting to create Site with body:\n\t "%s"\n\tvia url: %s', site_json, url)

    # Initialize loop with first request
    try:
        response = requests.post(url,
                                 headers = {'Content-Type': 'application/json'},
                                 data = site_json,
                                 auth=config.basic_auth)
    except requests.exceptions.RequestException as e:
        _logger.error(config.ERR_REQUEST_EXCEPTION_CODE, url, repr(e))
        return None

    # If the response from the first attempt is a 409, find the existing site
    # and update the ID and try again.
    if response.status_code in [409]:
        existing_site = _get_site(site_obj['name'])
        if existing_site is not None:
            site_obj['id'] = existing_site['id']
        _logger.debug('Retrying to create Site after 409 with body:\n\t "%s"\n\tvia url: %s', site_json, url)
        try:
            response = requests.post(url,
                                    headers = {'Content-Type': 'application/json'},
                                    data = json.dumps(site_obj),
                                    auth=config.basic_auth)
        except requests.exceptions.RequestException as e:
            _logger.error(config.ERR_REQUEST_EXCEPTION_CODE, url, repr(e))
            return None

    # If the initial response fails, log and return null
    if response.status_code not in [200, 201]:
        _log_xm_error(url, response)
        return None

    # Process the response
    site_obj = response.json()
    _logger.info('Created/Updated Site "%s" - Id: %s', site_obj['name'], site_obj['id'])
    # _logger.debug('Created/Updated Site "%s" - json body: %s', site_obj['name'], pprint.pformat(site_obj))
    return site_obj

def _process_sites():
    """Reads and restored the instances Site objects

    Retrieves the Site object records from the file system and adds/updates
    them into the target xMatters instance.

    Args:
        None

    Return:
        None
    """
    with open(config.sites_filename) as sites_file:
        num_lines = 0
        num_sites = 0
        for site_json in sites_file:
            # Ignore the opening array markers ("[\n" and "]\n")
            if len(site_json) > 2:
                # Remove trailing ",\n" or trailing "\n"
                site_json = site_json[:-2] if site_json[-2:] == ',\n' else site_json[:-1]
                num_lines += 1
                site_obj = _add_site(site_json)
                _site_dict[site_obj['name']] = site_obj
                num_sites += 0 if site_obj == None else 1

    _logger.info("Restored %d of a possible %d Sites.", num_sites, num_lines)

def _get_site(name: str):
    """Get a site object by name

    Retrieves the Site object record from xMatters based on it's name.

    Args:
        name (str): Site name to retrieve

    Return:
        site (dict): The found site object
    """
    if name in _site_dict:
        _logger.debug('Found Site "%s"', name)
        return _site_dict[name]

    # Initialize conditions
    url = config.xmod_url + '/api/xm/1/sites/' + urllib.parse.quote(name)
    _logger.debug('Retrieving Site, url=%s', url)

    # Get the site records
    response = requests.get(url, auth=config.basic_auth)
    if response.status_code not in [200]:
        _log_xm_error(url, response)
        return None

    # Process the responses
    site = response.json()
    _site_dict[name] = site
    _logger.debug('Retrieved Site "%s"', name)

    return site

def _add_devices(user_id: str, target_name: str, devices: list):
    """Attempst to add the Device objects from the Device list.
        
    Creates Device objects based on the device_list
    
    Args:
        user_id (str): The UUID of the User to add the devices to
        target_name (str): The targetName field for the User to add devices to
        devices (list): The list object containing the Devices to add
    """
    dev_count = 0
    for device in devices:

        # Update the device
        device['owner'] = user_id
        del device['targetName']
        del device['links']
        if 'timeframes' in device:
            if device['timeframes']['total'] > 0 and 'data' in device['timeframes']:
                device['timeframes'] = device['timeframes']['data']
            else:
                del device['timeframes']

        # Set our resource URLs
        url = config.xmod_url + '/api/xm/1/devices'
        _logger.debug('Attempting to create Device "%s" for User Id "%s"\n\tvia url: %s\n\twith payload: %s', device['name'], user_id, url, json.dumps(device))

        # Initialize loop with first request
        try:
            response = requests.post(url,
                                    headers = {'Content-Type': 'application/json'},
                                    data = json.dumps(device),
                                    auth=config.basic_auth)
        except requests.exceptions.RequestException as e:
            _logger.error(config.ERR_REQUEST_EXCEPTION_CODE, url, repr(e))
            continue

        # If the initial response fails, log and return null
        if response.status_code not in [200, 201]:
            _log_xm_error(url, response)
            continue

        # Process the response
        user_device = response.json()
        _logger.info(f'Created/Updated Device "{target_name}|{user_device["name"]}" - Id: {user_device["id"]}')
        dev_count += 1
        # _logger.debug('Created/Updated Device "%s" - json body: %s', user_device['name'], pprint.pformat(user_device))

    _logger.debug(f'Added {dev_count} of a possible ' \
                f'{len(devices)} devices for ' \
                f'{target_name}')

    return dev_count

def _add_user(include_devices: bool, user_json: str):
    """Attempst to add a new User object from the JSON string.
        
    Creates a dict object to pass to xMatters to create a new User
    
    Args:
        include_devices (bool): If True, restore the User's devices too
        user_json (str): The JSON payload representing the User to add
    """
    # Convert the User JSON string to an object
    full_user_obj = json.loads(user_json)
    user_obj = full_user_obj['user']

    # Prepare the object for adding back in
    del user_obj['links']
    site = _get_site(user_obj['site']['name'])
    del user_obj['site']
    user_obj['site'] = site['id']
    role_list = []
    is_comp_admin = False
    for role in user_obj['roles']['data']:
        if role['name'] == 'Company Admin': is_comp_admin = True
        role_list.append(role['name'])
    # If a Company Admin, return as there is nothing to do
    if is_comp_admin: 
        _logger.warn('Unable to add internal xMatters User with Role "Company Admin": %s', 
            user_obj['firstName'] + ' ' + user_obj['lastName'] + ' (' + user_obj['targetName'] + ')')
        return

    # Continue user preprocessing
    del user_obj['roles']
    user_obj['roles'] = role_list

    # Build supervisors list to preserve after we get ID
    supervisors = []
    if 'supervisors' in user_obj:
        if user_obj['supervisors']['total'] > 0:
            for supervisor in user_obj['supervisors']['data']:
                supervisors.append(supervisor['targetName'])
        del user_obj['supervisors']
    user_obj['supervisors'] = []
            
    # Set our resource URLs
    url = config.xmod_url + '/api/xm/1/people'
    _logger.debug('Attempting to create User with body:\n\t "%s"\n\tvia url: %s', json.dumps(user_obj), url)

    # Initialize loop with first request
    try:
        response = requests.post(url,
                                 headers = {'Content-Type': 'application/json'},
                                 data = json.dumps(user_obj),
                                 auth=config.basic_auth)
    except requests.exceptions.RequestException as e:
        _logger.error(config.ERR_REQUEST_EXCEPTION_CODE, url, repr(e))
        return None

    # If the initial response fails, log and return null
    if response.status_code not in [200, 201]:
        _log_xm_error(url, response)
        return None

    # Process the response
    new_user_obj = response.json()
    _user_dict[new_user_obj['targetName']] = new_user_obj['id']
    _supervisor_dict[new_user_obj['id']] = supervisors

    # If we need to add devices, do that now
    dev_count = 0
    if include_devices:
        dev_count = _add_devices(new_user_obj['id'], new_user_obj['targetName'], full_user_obj['devices'])

    _logger.info(f'Created/Updated User "{new_user_obj["targetName"]}" - Id: {new_user_obj["id"]} '\
                 f'and added {dev_count} Devices.')
    #_logger.debug(f'Created/Updated User "{new_user_obj["targetName"]}" - Id: {new_user_obj["id"]} '\
    #             f'and added {dev_count} Devices.' \
    #             f'\n\tUser Obj: {pprint.pformat(new_user_obj)}')
    return user_obj

def _get_user(targetName: str):
    """Get a User's id by targetName

    Retrieves the User object record from xMatters based on it's targetName.

    Args:
        name (str): Target Name to retrieve

    Return:
        user_id (str): The found User ID
    """
    if targetName in _user_dict:
        user_id = _user_dict[targetName]
        _logger.debug('Found ID "%s" for User "%s"', user_id, targetName)
        return user_id

    # Initialize conditions
    url = config.xmod_url + '/api/xm/1/people/' + urllib.parse.quote(targetName)
    _logger.debug('Retrieving User, url=%s', url)

    # Get the site records
    response = requests.get(url, auth=config.basic_auth)
    if response.status_code not in [200]:
        _log_xm_error(url, response)
        _user_dict[targetName] = None
        return None

    # Process the responses
    user = response.json()
    _user_dict[user['targetName']] = user['id']
    _logger.debug('Retrieved User "%s"', user['targetName'])

    return user['id']

def _add_user_supervisors(user_id: str, target_name: str):
    """Attempts to update the new User object with supervisors.
        
    Updates Creates a dict object to pass to xMatters to create a new User
        
    Args:
        user_id (str): The User's Id to add supervisors
        target_name (str): The User's targetName to add supervisors
    """
    # Is there anything to do
    if not user_id in _supervisor_dict or len(_supervisor_dict[user_id]) == 0:
        _logger.debug('No supervisors for user_id: %s, target_name: %s', user_id, target_name) 
        return 0

    # Setup the update object
    user = {}
    user['id'] = user_id
    user['targetName'] = target_name
    supervisors = []
    for targetName in _supervisor_dict[user_id]:
        super_id = _get_user(targetName)
        if super_id:
            supervisors.append(super_id)
        else:
            _logger.warn('Unable to find Supervisor (%s) for User (%s).', targetName, target_name)
    if len(supervisors) == 0:
        _logger.debug('No valid supervisors for user_id: %s, target_name: %s', user_id, target_name) 
        return 0
    user['supervisors'] = supervisors

    # Set our resource URLs
    url = config.xmod_url + '/api/xm/1/people'
    _logger.debug('Attempting to update the Supervisors for User:\n\t "%s"\n\tvia url: %s', json.dumps(user), url)

    # Initialize loop with first request
    try:
        response = requests.post(url,
                                 headers = {'Content-Type': 'application/json'},
                                 data = json.dumps(user),
                                 auth=config.basic_auth)
    except requests.exceptions.RequestException as e:
        _logger.error(config.ERR_REQUEST_EXCEPTION_CODE, url, repr(e))
        return 0

    # If the initial response fails, log and return null
    if response.status_code not in [200, 201]:
        _log_xm_error(url, response)
        return 0

    # Process the response
    upd_user_obj = response.json()
    _logger.info('Updated Supervisors for User "%s" - Id: %s', upd_user_obj['targetName'], upd_user_obj['id'])
    # _logger.debug('Created/Updated User "%s" - json body: %s', upd_user_obj['targetName'], pprint.pformat(upd_user_obj))
    return 1

def _process_users(include_devices: bool):
    """Reads and restored the instances User objects

    Retrieves the Users object records from the file system and adds/updates
    them into the target xMatters instance.

    Args:
        include_devices (bool): If True, restore the User's devices too

    Return:
        None
    """
    # First add the users without supervisors
    with open(config.users_filename) as users_file:
        num_lines = 0
        num_users = 0
        for user_json in users_file:
            # Ignore the opening array markers ("[\n" and "]\n")
            if len(user_json) > 2:
                # Remove trailing ",\n" or trailing "\n"
                user_json = user_json[:-2] if user_json[-2:] == ',\n' else user_json[:-1]
                num_lines += 1
                user_obj = _add_user(include_devices, user_json)
                if user_obj:
                    _user_dict[user_obj['targetName']] = user_obj['id']
                    num_users += 0 if user_obj == None else 1

    _logger.info("Restored %d of a possible %d Users.", num_users, num_lines)

    # Next add the users supervisors
    num_users = 0
    user_dict = {x:y for x,y in _user_dict.items()}
    for target_name, user_id in user_dict.items():
        num_users += _add_user_supervisors(user_id, target_name)
    _logger.info("Updated supervisors for %d of a possible %d Users.", num_users, len(_user_dict))

def _process_devices():
    """Reads and restored the instances User's Device objects

    Retrieves the Users object records from the file system and adds/updates
    the associated Devices into the target xMatters instance.

    Args:
        None

    Return:
        None
    """
    _logger.info('Processing Devices independent of Users.')
    # Go through the Users file and pull out the device info
    with open(config.users_filename) as users_file:
        max_devices = 0
        num_devices = 0
        num_lines = 0
        for user_json in users_file:
            # Ignore the opening array markers ("[\n" and "]\n")
            if len(user_json) > 2:
                # Remove trailing ",\n" or trailing "\n"
                user_json = user_json[:-2] if user_json[-2:] == ',\n' else user_json[:-1]
                num_lines += 1
                full_user_obj = json.loads(user_json)
                user_obj = full_user_obj['user']
                max_devices += len(full_user_obj['devices'])
                # Try to get the "id" from the user dictionary, otherwise
                # retrieve "id" field directly from xMatters as it may have
                # changed upon recovery
                user_id = _get_user(user_obj['targetName'])
                num_devices += _add_devices(user_id, user_obj['targetName'], full_user_obj['devices'])

    _logger.info(f"Restored {num_devices} of a possible {max_devices} Devices from {num_lines} Users.")

def _get_group(targetName: str):
    """Get a Group's id by targetName

    Retrieves the Group object record from xMatters based on it's targetName.

    Args:
        name (str): Target Name to retrieve

    Return:
        user_id (str): The found User ID
    """
    if targetName in _group_dict:
        group_id = _group_dict[targetName]
        _logger.debug(f'Found ID "{group_id}" for Group "{targetName}"')
        return group_id

    # Initialize conditions
    url = config.xmod_url + '/api/xm/1/groups/' + urllib.parse.quote(targetName)
    _logger.debug('Retrieving Group, url=%s', url)

    # Get the site records
    response = requests.get(url, auth=config.basic_auth)
    if response.status_code not in [200]:
        _log_xm_error(url, response)
        _group_dict[targetName] = None
        return None

    # Process the responses
    group = response.json()
    _group_dict[group['targetName']] = group['id']
    _logger.debug(f'Retrieved Group "{group["targetName"]}"')

    return group['id']

def _get_shift(group_id: str, target_name: str, shift_name: str):
    """Get a Group's shift by name

    Retrieves the Group object's Shift record from xMatters based on it's name.

    Args:
        group_id (str): Group's UUID
        target_name (str): Group's name
        shift_name (str): Name of Shift to retrieve

    Return:
        shift_id (str): The found Shift ID
    """
    # Initialize conditions
    url = config.xmod_url + '/api/xm/1/groups/' + group_id + '/shifts/'+ urllib.parse.quote(shift_name)
    _logger.debug('Attempting to retrieve Shift, url=%s', url)

    # Get the site records
    response = requests.get(url, auth=config.basic_auth)
    if response.status_code in [404]:
        # Not found, ignore and return None
        _logger.debug(f'Shift {shift_name} was not found in {target_name}')
        return None
    elif response.status_code not in [200]:
        _log_xm_error(url, response)
        return None

    # Process the responses
    shift = response.json()
    _logger.debug(f'Retrieved Shift "{target_name}|{shift["name"]}"')

    return shift['id']

def _add_member(group_id: str, group_name: str, shift_name: str, member_obj: dict):
    """Attempst to add a new Member object to the specified Shift
        
    Creates a dict object to pass to xMatters to create a new Member in an
    existing Group and Shift.
        
    Args:
        group_id (str): The UUID of the Group to add the members to
        group_name (str): The targetName field for the Group to add members to
        shift_name (str): The targetName field for the Shift to add members to
        member_obj (str): The JSON payload representing the Membrer to add
    """
    # Prepare the object by processing Recipient
    del member_obj['shift']
    recip_type = member_obj['recipient']['recipientType']
    recip_target_name = member_obj['recipient']['targetName']
    del member_obj['recipient']
    member_obj['recipient'] = {}
    member_obj['recipient']['recipientType'] = recip_type
    if recip_type == 'GROUP':
        member_obj['recipient']['id'] = _get_group(recip_target_name)
    else:
        member_obj['recipient']['id'] = _get_user(recip_target_name)
    
    # Set our resource URLs
    url = config.xmod_url + '/api/xm/1/groups/' + group_id + '/shifts/' + urllib.parse.quote(shift_name) + '/members'
    _logger.debug(f'Attempting to add Shift Member with body:\n\t "{json.dumps(member_obj)}"\n\tvia url: {url}')

    # Perform request
    try:
        response = requests.post(url,
                                 headers = {'Content-Type': 'application/json'},
                                 data = json.dumps(member_obj),
                                 auth=config.basic_auth)
    except requests.exceptions.RequestException as e:
        _logger.error(config.ERR_REQUEST_EXCEPTION_CODE, url, repr(e))
        return None

    # If the initial response fails, log and return null
    if response.status_code not in [200, 201]:
        _log_xm_error(url, response)
        return None

    # Process the response
    new_obj = response.json()
    _logger.info(f'Created Shift Member "{recip_target_name}" - Id: {new_obj["recipient"]["id"]}')
    #_logger.debug(f'Created Shift Member "{recip_name}" - json body: {pprint.pformat(new_obj)}')
    return new_obj

def _del_shift(group_id: str, target_name: str, shift_name: str):
    """Attempst to remove an existing Shift
        
    Removes the Shift object from the named group in preparation for
    re-adding based on the shifts defined by the Group being recovered.
    
    Args:
        group_id (str): The UUID of the Group to add the shifts to
        target_name (str): The targetName field for the Group to add shifts to
        shift_name (str): The name of the shift to delete
    """
    # Set our resource URLs
    url = config.xmod_url + '/api/xm/1/groups/' + group_id + '/shifts/' + urllib.parse.quote(shift_name)
    _logger.debug(f'Attempting to delete Shift "{shift_name}" for Group "{target_name}"\n\tvia url: {url}')

    # Make request
    try:
        response = requests.delete(url,
                                auth=config.basic_auth)
    except requests.exceptions.RequestException as e:
        _logger.error(config.ERR_REQUEST_EXCEPTION_CODE, url, repr(e))
        return False

    # If the initial response fails, log and return null
    if response.status_code not in [200]:
        _log_xm_error(url, response)
        return False

    _logger.info(f'Deleted Shift "{shift_name}" from Group "{target_name}"')
    return True

class ResilientSession(Session):
    """
    This class is supposed to retry requests that return temporary errors.
    At this moment it supports: 501
    """

    def request(self, method, url, **kwargs):
        counter = 0

        while True:
            counter += 1

            r = super(ResilientSession, self).request(method, url, **kwargs)

            if r.status_code in [ 501, 502, 503, 504 ]:
                delay = 3 * counter
                _logger.warn("Got recoverable error [%s] from %s %s, retry #%s in %ss" % (r.status_code, method, url, counter, delay))
                time.sleep(delay)
                continue

            return r

def _add_shifts(group_id: str, target_name: str, shifts: list):
    """Attempst to add the Shift objects from the shifts list.
        
    Creates Shift objects based on the shifts list
    
    Args:
        group_id (str): The UUID of the Group to add the shifts to
        target_name (str): The targetName field for the Group to add shifts to
        shifts (list): The list object containing the Shifts to add
    """
    had_new_default_shift = False
    shift_count = 0
    for shift in shifts:

        # Denote the fact that this Group had a shift with the default name
        # If it did not, we will remove it later
        if shift['name'] == config.new_default_shift_name:
            had_new_default_shift = True
    
        # Delete any shift with matching name first, as we can't update an existin shift (yet)
        deleted_shift = _del_shift(group_id, target_name, shift['name'])

        # Update the shift
        del shift['group']
        del shift['links']
        del shift['members']
        del shift['id']

        # Set our resource URLs
        url = config.xmod_url + '/api/xm/1/groups/' + group_id + '/shifts'
        _logger.debug(f'Attempting to create Shift "{shift["name"]}" for Group Id "{group_id}"\n\tvia url: {url}\n\twith payload: {json.dumps(shift)}')

        # Make the request (using resilient session as _del_shift may take time to propogate)
        try:
            if deleted_shift:
                s = ResilientSession()
                response = s.post(url,
                                  headers = {'Content-Type': 'application/json'},
                                  data = json.dumps(shift),
                                  auth=config.basic_auth)
            else:
                response = requests.post(url,
                                        headers = {'Content-Type': 'application/json'},
                                        data = json.dumps(shift),
                                        auth=config.basic_auth)
        except requests.exceptions.RequestException as e:
            _logger.error(config.ERR_REQUEST_EXCEPTION_CODE, url, repr(e))
            continue

        # If the initial response fails, log and return null
        if response.status_code in [501]:
            _logger.info(f'Shift "{target_name}|{shift["name"]}" already exits.  Skipping.')
            continue
        elif response.status_code not in [200, 201]:
            _log_xm_error(url, response)
            continue

        # Process the response
        group_shift = response.json()
        _logger.info(f'Created Shift "{target_name}|{shift["name"]}" - Id: {group_shift["id"]}')
        shift_count += 1
        # _logger.debug(f'Created Shift "{group_shift["name"]}" - json body: {pprint.pformat(group_shift)}')

    # Before finishing, remove the New default shift name, if we did not have it before
    # (checks to see if the unused default shift exists first)
    if not had_new_default_shift:
        def_shift_id = _get_shift(group_id, target_name, config.new_default_shift_name)
        if def_shift_id is not None:
            _del_shift(group_id, target_name, config.new_default_shift_name)

    _logger.debug(f'Added {shift_count} of a possible ' \
                f'{len(shifts)} Shifts ' \
                f'for Group {target_name}')

    return shift_count

def _add_shift_members(group_id: str, target_name: str, shifts: list):
    """Attempst to add the Member objects from the shifts list.
        
    Creates Shift's Member objects based on the shifts list
    
    Args:
        group_id (str): The UUID of the Group to add the shifts to
        target_name (str): The targetName field for the Group to add shifts to
        shifts (list): The list object containing the Shifts to add
    """
    mem_count = 0
    for shift in shifts:

        members = []
        if 'members' in shift:
            if shift['members']['total'] > 0:
                for member in shift['members']['data']:
                    members.append(member)

        # Add the members back now
        for member in members:
            new_mem = _add_member(group_id, target_name, shift["name"], member)
            mem_count += 1 if new_mem is not None else 0

    _logger.debug(f'Added {mem_count} of a possible ' \
                f'{len(members)} Members ' \
                f'from {len(shifts)} Shifts, ' \
                f'for Group {target_name}')

    return mem_count

def _add_group(group_json: str):
    """Attempst to add a new Group object from the JSON string.
        
    Creates a dict object to pass to xMatters to create a new Group
    
    Args:
        group_json (str): The JSON payload representing the User to add
    """
    # Convert the User JSON string to an object
    full_group_obj = json.loads(group_json)
    group_obj = full_group_obj['group']

    # Prepare the object for adding back in
    del group_obj['links']
    if 'site' in group_obj:
        site = _get_site(group_obj['site'])
        if site is not None:
            group_obj['site'] = site['id']
        else:
            del group_obj['site']

    # Build supervisors list to preserve after we get ID
    if 'supervisors' in group_obj and group_obj['supervisors']['total'] > 0:
        supervisors = []
        for supervisor in group_obj['supervisors']['data']:
            super_id = _get_user(supervisor['targetName'])
            if super_id:
                supervisors.append(super_id)
            else:
                _logger.warn(f'Unable to find Supervisor ({supervisor["targetName"]}) for Group ({group_obj["targetName"]}).')
        del group_obj['supervisors']
        if len(supervisors) > 0:
            group_obj['supervisors'] = supervisors
            
    # Set our resource URLs
    url = config.xmod_url + '/api/xm/1/groups'
    _logger.debug(f'Attempting to create Group with body:\n\t "{json.dumps(group_obj)}"\n\tvia url: {url}')

    # Initialize loop with first request
    try:
        response = requests.post(url,
                                 headers = {'Content-Type': 'application/json'},
                                 data = json.dumps(group_obj),
                                 auth=config.basic_auth)
    except requests.exceptions.RequestException as e:
        _logger.error(config.ERR_REQUEST_EXCEPTION_CODE, url, repr(e))
        return None

    # If the initial response fails, log and return null
    if response.status_code not in [200, 201]:
        _log_xm_error(url, response)
        return None
    is_new = True if response.status_code == 201 else False

    # Process the response
    new_group_obj = response.json()
    _group_dict[new_group_obj['targetName']] = new_group_obj['id']

    _logger.info(f'{"Created" if is_new else "Updated"} Group "{new_group_obj["targetName"]}" ' \
                 f'- Id: {new_group_obj["id"]}.')
    # _logger.debug(f'Created/Updated User "{new_group_obj["targetName"]}" - json body: {pprint.pformat(new_group_obj)}')
    return { 'is_new': is_new, 'group_obj': group_obj }

def _process_shifts():
    """Reads and restored the instances Group's Shift objects

    Retrieves the Groups object records from the file system and adds/updates
    the associated Shifts into the target xMatters instance.

    Args:
        None

    Return:
        None
    """
    _logger.info('Processing Shifts.')
    # first Go through the Groups add all the Shifts
    with open(config.groups_filename) as groups_file:
        max_shifts = 0
        num_shifts = 0
        num_lines = 0
        for group_json in groups_file:
            # Ignore the opening array markers ("[\n" and "]\n")
            if len(group_json) > 2:
                # Remove trailing ",\n" or trailing "\n"
                group_json = group_json[:-2] if group_json[-2:] == ',\n' else group_json[:-1]
                num_lines += 1
                full_group_obj = json.loads(group_json)
                group_obj = full_group_obj['group']
                max_shifts += len(full_group_obj['shifts'])
                # Try to get the "id" from the group dictionary, otherwise
                # retrieve "id" field directly from xMatters as it may have
                # changed upon recovery
                group_id = _get_group(group_obj['targetName'])
                num_shifts += _add_shifts(group_id, group_obj['targetName'], full_group_obj['shifts'])
        _logger.info(f"Restored {num_shifts} of a possible {max_shifts} Shifts from {num_lines} Groups.")

    # Now go through the Shifts
    _logger.info('Processing Shift Members.')
    with open(config.groups_filename) as groups_file:
        max_members = 0
        num_members = 0
        num_shifts = 0
        num_lines = 0
        for group_json in groups_file:
            # Ignore the opening array markers ("[\n" and "]\n")
            if len(group_json) > 2:
                # Remove trailing ",\n" or trailing "\n"
                group_json = group_json[:-2] if group_json[-2:] == ',\n' else group_json[:-1]
                num_lines += 1
                full_group_obj = json.loads(group_json)
                group_obj = full_group_obj['group']
                # Count max Members
                num_shifts += len(full_group_obj['shifts'])
                for shift in full_group_obj['shifts']:
                    max_members += shift['members']['total']
                # Try to get the "id" from the group dictionary, otherwise
                # retrieve "id" field directly from xMatters as it may have
                # changed upon recovery
                group_id = _get_group(group_obj['targetName'])
                num_members += _add_shift_members(group_id, group_obj['targetName'], full_group_obj['shifts'])
        _logger.info(f"Restored {num_members} of a possible {max_members} Members from {num_shifts} Shifts in {num_lines} Groups.")

def _process_groups(include_shifts: bool):
    """Reads and restored the instances Groups objects

    Retrieves the Groups object records from the file system and adds/updates
    them into the target xMatters instance.

    Args:
        include_shifts (bool): If True, restore the Group's shifts too

    Return:
        None
    """
    # Iterate through and add all the groups first
    with open(config.groups_filename) as groups_file:
        num_lines = 0
        num_new_groups = 0
        num_updated_groups = 0
        for group_json in groups_file:
            # Ignore the opening array markers ("[\n" and "]\n")
            if len(group_json) > 2:
                # Remove trailing ",\n" or trailing "\n"
                group_json = group_json[:-2] if group_json[-2:] == ',\n' else group_json[:-1]
                num_lines += 1
                group_obj = _add_group(group_json)
                if group_obj:
                    num_new_groups += 1 if group_obj['is_new'] else 0
                    num_updated_groups += 0 if group_obj['is_new'] else 1

    _logger.info(f"Restored {num_new_groups} new Groups and updated {num_updated_groups} existing Groups from a possible {num_lines} Groups.")

    # Once the groups are added, then add the shifts (if requested)
    if include_shifts:
        _process_shifts()


def process(objects_to_process: list):
    """Capture objects for this instance.

    If requeste contains 'sites', then read and restore Sites.
    If requeste contains 'users', then read and restore Users.
    If requeste contains 'devices', then read and restore Devices.
    If requeste contains 'groups', then read and restore Groups.

    Args:
        objects_to_process (list): The list of object types to restore.
    """
    global _logger # pylint: disable=global-statement

    ### Get the current logger
    _logger = common_logger.get_logger()

    # Read and restore the Site objects
    if 'sites' in objects_to_process:
        _process_sites()

    # Read and restore the User objects, and possibly devices
    if 'users' in objects_to_process:
        _process_users('devices' in objects_to_process)
    elif 'devices' in objects_to_process:
        _process_devices()

    # Read and restore the Group objects
    if 'groups' in objects_to_process:
        _process_groups('shifts' in objects_to_process)
    elif 'shifts' in objects_to_process:
        _process_shifts()

def main():
    """In case we need to execute the module directly"""
    pass

if __name__ == '__main__':
    main()
