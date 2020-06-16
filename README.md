# Restore xMatters Instance Data (restore-instance-data.py)

A Python utility to restore the xMatters Instance data that was preservved with the [Capture xMatters Instance Data](https://github.com/xmatters/xm-labs-capture-instance-data) to help in recovering from an unforseen catastrophe.  The script currently restores the following information:

* Sites
* Users
* Devices with Timeframes
* Groups and Shifts
  * **Caveat**: Group Observers are not able to be restored at this time, and will have to be manually re-established once the Groups have been recovered.  Once the xMatters [`Get a group xM API`](https://help.xmatters.com/xmapi/index.html#get-a-group) and [`Create a group xM API`](https://help.xmatters.com/xmapi/index.html#create-a-group) can handle capturing and restoring those values, we can include them.

**Note**: This has beeen superseeded by the [xmtoolbox](https://github.com/xmatters/xmtoolbox-quick-start)


The information is read from the timestamped files previously captured so that you can run this via automation as often as you like.  The file formats are dependent on the type of information, and are expected to be in a JSON (JavaScript Object Notation) format.  This makes it easier for recovery.

 One important caveat is that an xMatters Instance is also formed based on a set of Administrative Data that is unable to be captured or restored from an automated perspective.  The `capture` utility creates a file that lists the Administrative Objects that are in use by the captured data.  These Administrative Objects will need to either already exists in the environment being restored, or be re-created with the same exact same names (Spelling, capitalization, punctuation):

* Roles (and their associated Function),
* Countrys,
* Languages,
* Time Zones,
* Device Names, and
* User Service Providers (the internal handlers for the various Device Types)

This information may be given to xMatters Support, who can help with ensuring that your target environment is ready for recovery by this utility.

![alt](https://github.com/xmatters/xMatters-Labs/raw/master/media/disclaimer.png)

## Pre-Requisites

* [Python 3.7.1](https://www.python.org/downloads/release/python-371/) (I recommend using [pyenv](https://github.com/pyenv/pyenv) to get and manage your python installations)
* Python [requests](http://docs.python-requests.org/en/master/) module (`pip install requests`)
* Details for the xMatters instance to be captured (e.g. Non-Production vs Production, URL, a Company Supervisor's API Key and Secret, etc.)

## Files

* [restore-instance-data.py](restore-instance-data.py) - Main driver/starting point.
* [config.py](config.py) - Defines the config object used by the program, and error messages
* [common_logger.py](common_logger.py) - Provides logging capabilities to the utility.
* [cli.py](cli.py) - The Command Line processor that handles dealing with command line arguments, as well as rading the defaults.json file.
* [processor.py](processor.py) - The guts of the utility where all of the interactions from the local file system to xMatters occurs.
* [defaults.json](defaults.json) - Example default property settings.  You may override these with command line arguments too.

## How it works

The utility expects several inputs via the command-line (and optionally the defaults file) to get started.  The inputs tell the utility where the existing files are located, the xMatters instance to recover, and which specific information you want to have restored:

* `all` - The most common case; restores Sites, Users, Devices (and Timeframes), Groups (and Shifts).
* `sites` - Just Sites
* `users` - Users and Devices and Timeframes
* `users-only` - Just Users (not Devices and Timeframes)
* `devices` - Just Devices and Timeframes
* `groups` - Just Groups and Shifts
* `groups-only` - Just Groups (not Shifts)
* `shifts` - Just Shifts (not Groups)

Upon specifying the inputs, the utility runs until completion as it retrieves the requested data from the files system, and writes tha informaiton to your xMatters instance.  The locations of the input files, and their filename based on the supplied Timestamp may be specified via the command line or the defauts file too.

## Installation

### Python / pyenv setup

* [Python 3.7.1](https://www.python.org/downloads/release/python-371/) (I recommend using [pyenv](https://github.com/pyenv/pyenv) to get and manage your python installations)
* After pyenv is installed, go to the directory where you downloaded the files from this repository.
   1. `pyenv install 3.7.1` - Installs Python v3.7.1 into your local system (You only need to do this once)
   2. `pyenv local 3.7.1` - Makes Python v3.7.1 the default for _this_ project (you only need to do this once per project)
   3. _[For Linux/Max OS X]_ - `eval "$(pyenv init -)"` - Initializes pyenv for command line access to Python  (you need to do this whenver you open a Terminal windows unless you do step 5 below)
   4. _[For Linux/Mac OS X]_ - `pyenv shell 3.7.1` - Sets up access to Pythons tools from the command line (e.g. `pip`)
   5. `echo 'eval "$(pyenv init -)"' >> ~/.bash_profile` - makes sure Pyenv is initialized whenver you open a Terminal window.
   6. _[Optional]_ `pyenv global 3.7.1` - Sets Python v3.7.1 as your global instance of Python
* Install the Python [requests](http://docs.python-requests.org/en/master/) module
  * `pip install requests`

### restore-instance-data.py setup

All you need to do now is to create an appropriate [defaults.json](defaults.json).  Use the included version for an example:

In place of `user` and `password`, it is recommended to generate an [API Key and Secret](https://help.xmatters.com/ondemand/user/apikeys.htm) and use those in place of the user and password. The key inherits the roles associated with the user who generated it. 

```text
   {

   // Your xMatters base instances base URL
   "xmodURL": "https://<mycompany>.<myserver>.xmatters.com",

   // An xMatters User ID with the "Company Supervisor" Role
   "user": "MyUser",

   // The User's Password
   "password": "MyPassword",

   // The directory to place output and log files
   // (the default is the current directory)
   "outDirectory": ".",

   // The character used between directory paths.
   // (change to \ for Windows)
   "dirSep": "/",

   // The base part of the file name to use for restored data
   // e.g. "restored-data"
   "baseName": "BASE-FILE-NAME-FOR-RESTORED-DATA",

   // The base part of the file name to use for runtime logging
   // e.g. "restored-data-logging"
   "logFilename": "restore-instance-data-results",

   // Corresponds to the level of details you want in the log file
   // (0=only errors, 1=only warnings, 2=info)
   "verbosity": 0,

   // Identifies whether the captured information is from your
   // Non-Production or Production instance
   "instance":  "np|prod",

   // The timestamp of the files to restore
   "timeStr": "YYYYMMDD-HHMM"
   }
```

## Running

Run one of these commands:

* Restore Everything
  * `python3 restore-instance-data.py -v -c -d defaults.json -i np -t 20181220-0307 all`
  * Example Input Filenames:
    * my-instance.np.sites.20181220-0307.json
    * my-instance.np.users.20181220-0307.json
    * my-instance.np.groups.20181220-0307.json
    * my-instance.np.restore-results.20181220-0307.log

* Restore Sites only
  * `python3 restore-instance-data.py -v -c -d defaults.json -i np -t 20181220-0307 sites`
  * Example Input Filenames:
    * my-instance.np.sites.20181220-0307.json
    * my-instance.np.restore-results.20181220-0307.log

* Restore Users only
  * `python3 restore-instance-data.py -v -c -d defaults.json -i np -t 20181220-0307 users`
  * Example Input Filenames:
    * my-instance.np.users.20181220-0307.json
    * my-instance.np.restore-results.20181220-0307.log

* Restore Devices and Timeframes only
  * `python3 restore-instance-data.py -v -c -d defaults.json -i np -t 20181220-0307 devices`
  * Example Input Filenames:
    * my-instance.np.users.20181220-0307.json
      * Users file contains Devices and Timeframes too
    * my-instance.np.restore-results.20181220-0307.log

* Restore Groups and Shifts only
  * `python3 restore-instance-data.py -v -c -d defaults.json -i np -t 20181220-0307 groups`
  * Example Input Filenames:
    * my-instance.np.groups.20181220-0307.json
    * my-instance.np.restore-results.20181220-0307.log

## Usage / Troubleshooting

```help
usage: restore-instance-data.py [-h] [-b BASE_NAME] [-c]
                                [-d DEFAULTS_FILENAME] [-i {np,prod}]
                                [-l LOG_FILENAME] [-o OUT_DIRECTORY]
                                [-p [PASSWORD]] [-t TIME_STR] [-u USER] [-V]
                                [-v] [-x XMOD_URL]
                                {sites,users,users-only,devices,groups,groups-only,shifts,all}
                                ...

  Created by jolin@xmatters.com on 2018-12-14.
  Copyright 2018 xmatters, Inc. All rights reserved.

  Licensed under the Apache License 2.0
  http://www.apache.org/licenses/LICENSE-2.0

  Distributed on an "AS IS" basis without warranties
  or conditions of any kind, either express or implied.

USAGE

positional arguments:
  {sites,users,users-only,devices,groups,groups-only,shifts,all}
    sites               Use this command in order to only read and restore
                        Sites.
    users               Use this command in order to only read and restore
                        Uses, including their Devices.
    users-only          Use this command in order to only read and restore
                        Uses, excluding their Devices.
    devices             Use this command in order to only read and restore
                        Devices.
    groups              Use this command in order to only read and restore
                        Groups (includes Shifts).
    groups-only         Use this command in order to only read and restore
                        Groups, excluding their Shifts.
    shifts              Use this command in order to only read and restore
                        Shifts.
    all                 Use this command in order to restore all objects to
                        the instance: Sites, Users, Devices, Groups, Shifts.

optional arguments:
  -h, --help            show this help message and exit
  -b BASE_NAME, --basename BASE_NAME
                        If not specified in the defaults file, use -b to
                        specify the base name of the input file. The names ie
                        expected to have a timestamp and .json appended to the
                        end.
  -c, --console         If specified, will echo all log output to the console
                        at the requested verbosity based on the -v option
  -d DEFAULTS_FILENAME, --defaults DEFAULTS_FILENAME
                        Specifes the name of the file containing default
                        settings [default: defaults.json]
  -i {np,prod}, --itype {np,prod}
                        Specifies whether we are updating the Production
                        (prod) or Non-Production (np) instance. [default: np]
  -l LOG_FILENAME, --lfile LOG_FILENAME
                        If not specified in the defaults file, use -l to
                        specify the base name of the log file. The name will
                        have a timestamp and .log appended to the end.
  -o OUT_DIRECTORY, --odir OUT_DIRECTORY
                        If not specified in the defaults file, use -o to
                        specify the file system location where the output
                        files were written.
  -p [PASSWORD]         If not specified in the defaults file, use -p to
                        specify a password either on the command line, or be
                        prompted
  -t TIME_STR, --time TIME_STR
                        If not specified in the defaults file, use -t to
                        specify the time string used in the data files to
                        read.
  -u USER, --user USER  If not specified in the defaults file, use -u to
                        specify the xmatters user id that has permissions to
                        get Event and Notification data.
  -V, --version         show program's version number and exit
  -v                    set verbosity level. Each occurrence of v increases
                        the logging level. By default it is ERRORs only, a
                        single v (-v) means add WARNING logging, a double v
                        (-vv) means add INFO logging, and a tripple v (-vvv)
                        means add DEBUG logging [default: 0]
  -x XMOD_URL, --xmodurl XMOD_URL
                        If not specified in the defaults file, use -i to
                        specify the base URL of your xmatters instance. For
                        example, 'https://myco.hosted.xmatters.com' without
                        quotes.

```

* You can add multiple "v"'s to the -v command line option.  
  * A single "-v" means only show errors and warnings
  * A double "-vv" means to show errors, warnings, and info statements
  * A tripple "-vvv" means to show errors, warnings, info, and debug statements
