#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# Check RTMP ffmpeg metrics
# 2026/04/01- Rulesets v1 for Check_MK 2.4 by swj67@protonmail.com - https://github.com/wjs67/check_mk_plugins


from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    Integer,
    LevelsType,
    SimpleLevels,
    Percentage,
    LevelDirection,
    validators,
    String,
)
from cmk.rulesets.v1.rule_specs import ActiveCheck, Topic

def _form_rtmp_ffmpeg_metrics():
   return Dictionary(
        title=Title("RTMP ffmpeg metrics"),
        help_text=Help("This check connects to a given rtmp-url and checks if online or not. "
                 "This check uses the active check <tt>check_rtmp</tt> [RULESETS.V1]. "),
        elements={
            "description": DictElement(
                parameter_form=String(
                    title=Title("<b>Service Description</b> field"),
                    custom_validate=(validators.LengthInRange(min_value=3),),
                ),
                required=True,
            ),
            "rtmp_url": DictElement(
                parameter_form = String(
                    title = Title("Set the RTMP-URL"),
                    custom_validate=(validators.LengthInRange(min_value=3),),
                ),
                required = True,
            ),
            # RTT Thresholds
            "rtt_levels": DictElement(
                required=True,
                parameter_form=SimpleLevels(
                    title=Title("RTT Levels:"),
                    help_text=Help("Set the levels for RTT in ms."),
                    form_spec_template=Integer(),
                    level_direction=LevelDirection.UPPER,
                    prefill_levels_type=DefaultValue(LevelsType.NONE),
                    prefill_fixed_levels=DefaultValue(value=(5, 20)),
                ),
            ),
            # Jitter Thresholds
            "jitter_levels": DictElement(
                required=True,
                parameter_form=SimpleLevels(
                    title=Title("Jitter Levels:"),
                    help_text=Help("Set the levels for Jitter in ms."),
                    form_spec_template=Integer(),
                    level_direction=LevelDirection.UPPER,
                    prefill_levels_type=DefaultValue(LevelsType.NONE),
                    prefill_fixed_levels=DefaultValue(value=(15, 30)),
                ),
            ),
            # Packet Loss Thresholds
            "packet_loss_levels": DictElement(
                required=True,
                parameter_form=SimpleLevels(
                    title=Title("Packet Loss Levels:"),
                    help_text=Help("Set the levels for Packet Loss in %."),
                    form_spec_template=Percentage(),
                    level_direction=LevelDirection.UPPER,
                    prefill_levels_type=DefaultValue(LevelsType.NONE),
                    prefill_fixed_levels=DefaultValue(value=(0.5, 2.0)),
                ),
            ),
            # FPS Thresholds
            "fps_levels": DictElement(
                required=True,
                parameter_form=SimpleLevels(
                    title=Title("FPS Levels:"),
                    help_text=Help("Set the levels for FPS."),
                    form_spec_template=Integer(),
                    level_direction=LevelDirection.LOWER,
                    prefill_levels_type=DefaultValue(LevelsType.NONE),
                    prefill_fixed_levels=DefaultValue(value=(27, 24)),
                ),
            ),
            # BPP Thresholds
            "bpp_levels": DictElement(
                required=True,
                parameter_form=SimpleLevels(
                    title=Title("BPP Levels:"),
                    help_text=Help("Set the levels for BPP in %."),
                    form_spec_template=Percentage(),
                    level_direction=LevelDirection.LOWER,
                    prefill_levels_type=DefaultValue(LevelsType.NONE),
                    prefill_fixed_levels=DefaultValue(value=(80.0, 60.0)),
                ),
            ),
            # Bitrate Thresholds
            "bitrate_levels": DictElement(
                required=True,
                parameter_form=SimpleLevels(
                    title=Title("Bitrate Levels:"),
                    help_text=Help("Set the levels for Bitrate in %."),
                    form_spec_template=Percentage(),
                    level_direction=LevelDirection.LOWER,
                    prefill_levels_type=DefaultValue(LevelsType.NONE),
                    prefill_fixed_levels=DefaultValue(value=(70.0, 50.0)),
                ),
            ),
            # Q-Score Thresholds
            "q_score_levels": DictElement(
                required=True,
                parameter_form=SimpleLevels(
                    title=Title("Q-Score Levels:"),
                    help_text=Help("Set the levels for Q-Score in %."),
                    form_spec_template=Percentage(),
                    level_direction=LevelDirection.LOWER,
                    prefill_levels_type=DefaultValue(LevelsType.NONE),
                    prefill_fixed_levels=DefaultValue(value=(85.0, 70.0)),
                ),
            ),
        }
    )

rule_spec_rtmp_ffmpeg_metrics = ActiveCheck(
    name="rtmp_ffmpeg_metrics",
    title=Title("RTMP ffmpeg metrics"),
    topic=Topic.APPLICATIONS,
    parameter_form = _form_rtmp_ffmpeg_metrics,
)


