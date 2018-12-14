"""Queries for and restores xmatters instance data

.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html

"""

import json
import sys
import pprint
from io import TextIOBase
import urllib.parse

import requests
from requests.auth import HTTPBasicAuth
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter, column_index_from_string

import config
import common_logger

_logger = None
_users = None

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
        _logger.error(config.ERR_INITIAL_REQUEST_FAILED_MSG,
                      response.status_code, url)
        _logger.error('Response - code: %s, reason: %s, message: %s',
                    str(body['code']) if 'code' in body else "none",
                    str(body['reason']) if 'reason' in body else "none",
                    str(body['message']) if 'message' in body else "none")

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
        
        Creates a dict object to pass to xMatters to create a new site
        
        Args:
        site_json: The JSON payload representing the site to add
    """
    # C
    site_obj = json.loads(site_json)
    
    # Set our resource URLs
    url = config.xmod_url + '/api/xm/1/sites'
    _logger.debug('Attempting to create site with body:\n\t "%s"\n\tvia url: %s', site_json, url)

    # Initialize loop with first request
    try:
        response = requests.post(url,
                                 headers = {'Content-Type': 'application/json'},
                                 data = site_json,
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
                num_sites += 0 if site_obj == None else 1

    _logger.debug("Restored %d of a possible %d Sites.", num_sites, num_lines)

def _process_users():
    """Reads and restored the instances User objects

    Retrieves the Users object records from the file system and adds/updates
    them into the target xMatters instance.

    Args:
        None

    Return:
        None
    """
    pass

def _process_devices():
    """Reads and restored the instances User's Device objects

    Retrieves the User's Device object records from the file system and adds/updates
    them into the target xMatters instance.

    Args:
        None

    Return:
        None
    """
    pass

def _process_groups():
    """Reads and restored the instances Groups objects

    Retrieves the Groups object records from the file system and adds/updates
    them into the target xMatters instance.

    Args:
        None

    Return:
        None
    """
    pass

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

    # Capture and save the Site objects
    if 'sites' in objects_to_process:
        _process_sites()

    # Capture and save the User objects
    if 'users' in objects_to_process:
        _process_users()

    # Capture and save the Device objects
    if 'devices' in objects_to_process:
        _process_devices()

    # Capture and save the Device objects
    if 'groups' in objects_to_process:
        _process_groups()

def main():
    """In case we need to execute the module directly"""
    pass

if __name__ == '__main__':
    main()
