#!/usr/bin/env python3
# Original source files: ~/share/doc/check_mk/treasures/modbus
# 2025-03-17: Migrated to CMK v2.4 - API rulesets.v1, by swj67[at]protonmail[dot]com
# -----------------------------------

from cmk.rulesets.v1 import Title, Help
from cmk.rulesets.v1.form_specs import (
    Dictionary,
    DictElement,
    List,
    SingleChoice,
    SingleChoiceElement,
    String,
    Integer,
    DefaultValue,
)
from cmk.rulesets.v1.form_specs.validators import LengthInRange, NumberInRange
from cmk.rulesets.v1.rule_specs import SpecialAgent, Topic

def _valuespec_special_agent_modbus():

    return Dictionary(
        title = Title("Check Modbus devices"),
        help_text=Help(
            "Configure the Server Address and the ids you want to query from the device"
            "Please refer to the documentation of the device to find out which ids you want"
        ),
        elements = {
            "port": DictElement(
                parameter_form = Integer(
                    title = Title("Port"),
                    prefill = DefaultValue(502),
                ),
                required = True,
            ),
            "slave": DictElement(
                parameter_form=Integer(
                    title=Title("slave"),
                    help_text=Help(
                        "Valid slave device addresses are in the range of 0 – 247 decimal. "
                        "For Schneider SLAVE ID = 255."
                    ),
                    prefill=DefaultValue(255),
                    custom_validate=[
                        NumberInRange(min_value=1, max_value=255, error_msg=None),
                    ],
                ),
                required = True,
            ),
            "valores": DictElement(
                parameter_form = List(
                    title = Title("Values"),
                    help_text = Help("List of parameters for querying the modbus server."),
                    element_template = Dictionary(
                        elements = {
                            "cid": DictElement(
                                parameter_form = Integer(
                                    title = Title("Register ID"),
                                ),
                                required = True,
                            ),
                            "words": DictElement(
                                parameter_form=SingleChoice(
                                    title=Title("Number of words"),
                                    elements=[
                                        SingleChoiceElement(name="One", title=Title("1 word")),
                                        SingleChoiceElement(name="Two", title=Title("2 words")),
                                    ],
                                    prefill=DefaultValue("One"),
                                ),
                                required=True,
                            ),
                            "ctype": DictElement(
                                parameter_form=SingleChoice(
                                    title=Title("Value Type"),
                                    elements=[
                                        SingleChoiceElement(name="counter", title=Title("Its a counter value")),
                                        SingleChoiceElement(name="gauge", title=Title("Its a gauge value")),
                                    ],
                                    prefill=DefaultValue("counter"),
                                ),
                                required = True,
                            ),
                            "name": DictElement(
                                parameter_form = String(
                                    title = Title("Register Name"),
                                    custom_validate=(LengthInRange(min_value=3),),
                                ),
                                required = True,
                            ),
                        },
                    )
                ),
            ),
        },
    )

rule_spec_service_counter = SpecialAgent(
    name = "modbus",
    topic = Topic.APPLICATIONS,
    parameter_form = _valuespec_special_agent_modbus,
    title = Title("Check Modbus devices"),
)


