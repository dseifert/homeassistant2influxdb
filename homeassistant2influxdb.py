#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import json
import yaml

# MySQL / MariaDB
from MySQLdb import connect as mysql_connect, cursors

# SQLite (not tested)
#import sqlite3

# progress bar
from tqdm import tqdm

# to apply the configuration schema for InfluxDB component
import voluptuous as vol

# let's recycle the code from the Home Assistant components
import sys
sys.path.append("home-assistant-core")
from homeassistant.helpers import location
from homeassistant.core import Event, State
from homeassistant.components.influxdb import get_influx_connection, _generate_event_to_json, INFLUX_SCHEMA
from homeassistant.exceptions import InvalidEntityFormatError

def rename_entity_id(old_name):
    """
    Given an entity_id, rename it to something else. Helpful if ids changed
    during the course of history and you want to quickly merge the data. Beware
    that no further adjustment is done, also no checks whether the referred
    sensors are even compatible.
    """
    rename_table = {
        "sensor.old_entity_name": "sensor.new_entity_name",
    }

    if old_name in rename_table:
        return rename_table[old_name]

    return old_name

def rename_friendly_name(attributes):
    """
    Given the attributes to be stored, replace the friendly name. Helpful
    if names changed during the course of history and you want to quickly
    correct the naming.
    """
    rename_table = {
        "Old Sensor Name": "New Sensor Name",
    }

    if "friendly_name" in attributes and attributes["friendly_name"] in rename_table:
        # print("renaming %s to %s" % (attributes["friendly_name"], rename_table[attributes["friendly_name"]]))
        attributes["friendly_name"] = rename_table[attributes["friendly_name"]]

    return attributes

def main():
    """
    Connect to both databases and migrate data
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('--user', '-u',
                        dest='user', action='store', required=True,
                        help='MySQL/MariaDB username')
    parser.add_argument('--password', "-p",
                        dest='password', action='store',
                        help='MySQL/MariaDB password')
    parser.add_argument('--host', '-s',
                        dest='host', action='store', required=True,
                        help='MySQL/MariaDB host')
    parser.add_argument('--database', '-d',
                        dest='database', action='store', required=True,
                        help='MySQL/MariaDB database')
    parser.add_argument('--count', '-c',
                        dest='row_count', action='store', required=False, type=int, default=0,
                        help='If 0 (default), determine upper bound of number of rows by querying database, '
                             'otherwise use this number (used for progress bar only)')

    args = parser.parse_args()

    # load InfluxDB configuration file (the one from Home Assistant) (without using !secrets)
    with open("influxdb.yaml") as config_file:
        influx_config = yaml.load(config_file, Loader=yaml.FullLoader)

    # validate and extend config
    schema = vol.Schema(INFLUX_SCHEMA, extra=vol.ALLOW_EXTRA)
    influx_config = schema(influx_config)

    # establish connection to InfluxDB
    influx = get_influx_connection(influx_config, test_write=True, test_read=True)
    converter = _generate_event_to_json(influx_config)

    # connect to MySQL/MariaDB database
    connection = mysql_connect(host=args.host, user=args.user, password=args.password, database=args.database, cursorclass=cursors.SSCursor, charset="utf8")
    cursor = connection.cursor()

    # untested: connect to SQLite file instead (you need to get rid of the first three `add_argument` calls above)
    #connection = sqlite3.connect('home_assistant_v2.db')

    if args.row_count == 0:
        # query number of rows in states table - this will be more than the number of rows we
        # are going to process, but at least it gives us some percentage and estimation
        cursor.execute("select COUNT(*) from states")
        total = cursor.fetchone()[0]
    else:
        total = args.row_count

    # select the values we are interested in
    cursor.execute("select states.entity_id, states.state, states.attributes, events.event_type, events.time_fired from states, events where events.event_id = states.event_id")

    # map to count names and number of measurements for each entity
    statistics = {}

    # convert each row, write to influxdb in batches
    batch_size_max = 512
    batch_size_cur = 0
    batch_json = []
    with tqdm(total=total, mininterval=1, unit=" rows", unit_scale=True) as progress_bar:
        for row in cursor:
            progress_bar.update(1)

            try:
                _entity_id = rename_entity_id(row[0])
                _state = row[1]
                _attributes_raw = row[2]
                _attributes = rename_friendly_name(json.loads(_attributes_raw))
                _event_type = row[3]
                _time_fired = row[4]
            except Exception as e:
                print("Failed extracting data from %s: %s.\nAttributes: %s" % (row, e, _attributes_raw))
                continue

            try:
                # recreate state and event
                state = State(
                    entity_id=_entity_id,
                    state=_state,
                    attributes=_attributes)
                event = Event(
                    _event_type,
                    data={"new_state": state},
                    time_fired=_time_fired
                )
            except InvalidEntityFormatError:
                pass
            else:
                data = converter(event)
                if not data:
                    continue

                # collect statistics (remove this code block to speed up processing slightly)
                if "friendly_name" in _attributes:
                    friendly_name = _attributes["friendly_name"]

                    if _entity_id not in statistics:
                        statistics[_entity_id] = {friendly_name:1}
                    elif friendly_name not in statistics[_entity_id]:
                        statistics[_entity_id][friendly_name] = 1
                        print("Found new name '%s' for entity '%s'. All names known so far: %s" % (friendly_name, _entity_id, statistics[_entity_id].keys()))
                        print(row)
                    else:
                        statistics[_entity_id][friendly_name] += 1

                batch_json.append(data)
                batch_size_cur += 1

                if batch_size_cur >= batch_size_max:
                    while True:
                        try:
                            influx.write(batch_json)
                        except Exception as e:
                            print(e)
                        else:
                            break
                    batch_json = []
                    batch_size_cur = 0


    while True:
        try:
            influx.write(batch_json)
        except Exception as e:
            print(e)
        else:
            break
    influx.close()

    # print statistics - ideally you have one friendly name per entity_id
    # you can use the output to see where the same sensor has had different
    # names, as well as which entities do not have lots of measurements and
    # thus could be ignored (add them to exclude/entities in the influxdb yaml)
    for entity in sorted(statistics.keys()):
        print(entity)
        for friendly_name in sorted(statistics[entity].keys()):
            count = statistics[entity][friendly_name]
            print("  - %s (%d)" % (friendly_name, count))

if __name__ == "__main__":
    main()
