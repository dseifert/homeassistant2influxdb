# Home Assistant - History to InfluxDB

## Important

As this script is used once and then (at least in theory) never again, I will
not be able to provide support or testing. Please check the forums as well as
any forks of the repo for potential updates by the community.

Quality of the script is also disputable given that it is a one-off. Use of
MySQL/MariaDB is hard-coded, but (untested) lines of code to work with the
SQLite dtabase are included (search for SQLite).

Use at your own risk. (Backups recommended)

## Introduction

Home Assistant's recorder component allows to store historical data in a database.
Database access is handled by SQLAlchemy, with the default database in SQLite.
MySQL/MariaDB is also quite popular and so is PostgreSQL.

However, if one wants to store a lot of data over a long period of time, neither
of these options gives the best performance. Instead, a dedicated time-series
keeping database format like InfluxDB allows best retrieval and storage of the
data.

However, if you only figure this out after already having assembled a huge amount
of historical data, there is no option to migrate your data.

This is an attempt to do exactly that. It is a one-off migration of data to
InfluxDB. Afterwards you should setup the InfluxDB integration to directly store
data to InfluxDB (and only keep a couple of days to few weeks at most in the
traditional database for the logbook and history components).

References:
- https://www.home-assistant.io/integrations/recorder/
- https://www.home-assistant.io/integrations/influxdb/

## Caveats

This script is rather simple and limited to my use-case. As it is a one-off
and I do not have other setups readily available, I limited it to the specific
task at hand. However, it should be easily adaptable.

Namely, this handles MySQL / MariaDB only. Adding SQLite, PostgreSQL etc could
be done trivially, I believe.

## Setup

In order to not duplicate logic, the script uses the InfluxDB component of
Home Assistant directly.

I've tested this on Ubuntu 18.04 with Python 3.7.

Setup:
1. `sudo apt install python3 python3.7-dev`
2. `git clone <this repository> migrate2influxdb`
3. `cd migrate2influxdb`
4. `git clone git@github.com:home-assistant/core.git home-assistant-core`
5. `python3 -m venv .venv`

Dependency installation:
1. `. .venv/bin/activate`
2. `pip install -r home-assistant-core/requirements.txt`
3. `pip install -r requirements.txt`

Run script:
1. Copy your InfluxDB configuration from Home Assistant to influxdb.yaml.
   This should be the file that you include via `influxdb: !include influx.yaml`
   in your installation (i.e. it does not start with `influxdb:\n`!).
   It must not include any !secret statements but rather the token (for v2)
   or user/password (for v1) explicitly
2. `. .venv/bin/activate`
3. `python homeassistant2influxdb.py ...` (see -h for options to specify your
   MariaDB/MySQL credentials)
