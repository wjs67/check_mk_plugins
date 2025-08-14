#!/usr/bin/env python3
# Author: wellingtonsilva67@gmail.com
# Version: 1.0 - 20250317 16:14
# -----------------------------------

import time
from cmk.agent_based.v2 import AgentSection, CheckPlugin, Service, Result, State

def parse_modbus(string_table):
    column_names = [
        "cid",
        "values",
        "ctype",
        "name",
    ]
    parsed = {}
    for line in string_table:
        parsed[line[0]] = {}
        for n in range(1, len(column_names)):
            parsed[line[0]][column_names[n]] = line[n]
    
    return parsed

agent_section_modbus = AgentSection(
    name = "modbus_value",
    parse_function = parse_modbus,
)

def discover_modbus(section):
   for cid in section:
      yield Service(item=section.get(cid).get('name'))

def check_modbus(item, section):
       for cid in section:
            name = section.get(cid).get('name')
            value = section.get(cid).get('values')
            if name == item and item is not None:
                yield Result(state=State.OK, summary=f"Current : {value} ({cid})")
            
            if item is None:
                yield Result(state=State.UNKNOWN, summary=f"Not found value for {item}")        
              
check_plugin_modbus = CheckPlugin(
    name = "modbus",
    sections = [ "modbus_value" ],
    service_name = "Modbus: %s",
    discovery_function = discover_modbus,
    check_function = check_modbus,
)


