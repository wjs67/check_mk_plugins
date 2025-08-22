#!/usr/bin/env python3
# Original source files: ~/share/doc/check_mk/treasures/modbus
# 2025-03-17: Migrated to CMK v2.4 - API server_side_calls.v1, by swj67[at]protonmail[dot]com
# -----------------------------------

from typing import Iterator
from pydantic import BaseModel
from cmk.server_side_calls.v1 import (
    HostConfig,
    SpecialAgentCommand,
    SpecialAgentConfig,
)

class ModbusParams(BaseModel):
    valores: list
    port: int
    slave: int

def generate_modbus_command(params: ModbusParams, host_config: HostConfig,) -> Iterator[SpecialAgentCommand]:
    #args = ['10.33.24.242 502 255 3701:1:counter:Power_Demand_Method 4190:1:counter:Mult-Tariff_Energy_Status']
    args: list[str] = [host_config.primary_ip_config.address, str(params.port), str(params.slave)]
    for valor in params.valores:
        args +=  [ ' ' + str(valor['cid'] )+ ':' + str(valor['words'].replace('One', '1').replace('Two', '2')) + ':' + str(valor['ctype']) + ':' + str(valor['name'].replace(' ', '_'))]


    yield SpecialAgentCommand(command_arguments=args)

special_agent_modbus = SpecialAgentConfig(
    name = "modbus",
    parameter_parser = ModbusParams.model_validate,
    commands_function = generate_modbus_command,
)

