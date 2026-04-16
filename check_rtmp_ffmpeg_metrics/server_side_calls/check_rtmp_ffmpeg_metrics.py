#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# Check RTMP ffmpeg metrics
# 2026/04/01- Server Side Calls for Check_MK 2.4 by swj67@protonmail.com - https://github.com/wjs67/check_mk_plugins

import shlex
import sys
from typing import Iterator, Any
from pydantic import BaseModel, field_validator, model_validator
from cmk.server_side_calls.v1 import ActiveCheckCommand, ActiveCheckConfig, HostConfig, noop_parser

def normalize_levels(v: Any, field_name: str) -> Any:
    """Normalize any levels data format to either None, ('NO_LIMITS',), or (warn, crit)
    
    Handles formats:
    - None: Not configured
    - ('no_levels', None): "No levels" explicitly selected -> ('NO_LIMITS',)
    - {'levels': None}: "No levels" explicitly selected -> ('NO_LIMITS',)
    - {'levels': ('fixed', (warn, crit))}: Fixed levels in nested tuple
    - {'levels': (warn, crit)}: Direct threshold tuple in dict
    - ('fixed', (warn, crit)): Type descriptor with values
    - (warn, crit): Direct numeric tuple
    """
    try:
        if v is None:
            return None
        
        # Handle tuple format from SimpleLevels - ('no_levels', None) or ('fixed', (w, c))
        if isinstance(v, tuple) and len(v) >= 1:
            # Check for 'no_levels' marker
            if v[0] == 'no_levels' or v[0] == 'NO_LIMITS':
                return ('NO_LIMITS',)
            
            # Check for type descriptor with nested tuple: ('fixed', (w, c))
            if isinstance(v[0], str) and len(v) > 1 and isinstance(v[1], (tuple, list)) and len(v[1]) >= 2:
                try:
                    w = float(v[1][0])
                    c = float(v[1][1])
                    return (w, c)
                except (TypeError, ValueError) as extract_err:
                    return None
            
            # Direct numeric tuple: (n1, n2)
            if len(v) >= 2:
                try:
                    w = float(v[0])
                    c = float(v[1])
                    return (w, c)
                except (TypeError, ValueError) as convert_err:
                    return None
        
        # Handle dict wrapper from SimpleLevels
        if isinstance(v, dict):
            if 'levels' not in v:
                return None
            
            levels_value = v.get('levels')
            
            # If 'levels' key exists but is None, user selected "No levels"
            if levels_value is None:
                return ('NO_LIMITS',)
            
            # Recursively process the nested value
            return normalize_levels(levels_value, field_name)
        
        return None
        
    except Exception as exc:
        return None

class RtmpParams(BaseModel):
    description: str
    rtmp_url: str
    timeout: int = 20
    rtt_levels: Any = None
    jitter_levels: Any = None
    packet_loss_levels: Any = None
    fps_levels: Any = None
    bpp_levels: Any = None
    bitrate_levels: Any = None
    q_score_levels: Any = None
    
    @model_validator(mode='before')
    @classmethod
    def log_raw_input(cls, data):
        """Log raw input before any validation"""
        return data
    
    @field_validator('rtt_levels', mode='before')
    @classmethod
    def validate_rtt(cls, v):
        return normalize_levels(v, 'rtt_levels')
    
    @field_validator('jitter_levels', mode='before')
    @classmethod
    def validate_jitter(cls, v):
        return normalize_levels(v, 'jitter_levels')
    
    @field_validator('packet_loss_levels', mode='before')
    @classmethod
    def validate_packet_loss(cls, v):
        return normalize_levels(v, 'packet_loss_levels')
    
    @field_validator('fps_levels', mode='before')
    @classmethod
    def validate_fps(cls, v):
        return normalize_levels(v, 'fps_levels')
    
    @field_validator('bpp_levels', mode='before')
    @classmethod
    def validate_bpp(cls, v):
        return normalize_levels(v, 'bpp_levels')
    
    @field_validator('bitrate_levels', mode='before')
    @classmethod
    def validate_bitrate(cls, v):
        return normalize_levels(v, 'bitrate_levels')
    
    @field_validator('q_score_levels', mode='before')
    @classmethod
    def validate_q_score(cls, v):
        return normalize_levels(v, 'q_score_levels')

def extract_thresholds(levels_data: Any, field_name: str) -> tuple[float, float] | None:
    """Extract (warn, crit) thresholds from normalized levels data
    
    Input should be from the validator, already normalized to:
    - None: Not configured
    - ('NO_LIMITS',): No limits selected
    - (float, float): Threshold values
    """
    if not levels_data:
        return None
    
    # Check for "No limits" marker
    if isinstance(levels_data, tuple) and len(levels_data) == 1 and levels_data[0] == 'NO_LIMITS':
        return (999999.0, 999999.0)
    
    # Expect (warn, crit) tuple with numeric values
    if isinstance(levels_data, (tuple, list)) and len(levels_data) >= 2:
        try:
            w = float(levels_data[0])
            c = float(levels_data[1])
            return (w, c)
        except (TypeError, ValueError, IndexError) as e:
            pass
    
    return None

def generate_rtmp_services(params: RtmpParams, host_config: HostConfig) -> Iterator[ActiveCheckCommand]:
    try:
        args = [shlex.quote(params.rtmp_url)]
        
        # Build command arguments with extracted thresholds
        thresholds = {
            'rtt': extract_thresholds(params.rtt_levels, 'rtt_levels'),
            'jitter': extract_thresholds(params.jitter_levels, 'jitter_levels'),
            'packet_loss': extract_thresholds(params.packet_loss_levels, 'packet_loss_levels'),
            'fps': extract_thresholds(params.fps_levels, 'fps_levels'),
            'bpp': extract_thresholds(params.bpp_levels, 'bpp_levels'),
            'bitrate': extract_thresholds(params.bitrate_levels, 'bitrate_levels'),
            'q_score': extract_thresholds(params.q_score_levels, 'q_score_levels'),
        }
        
        if thresholds['rtt']:
            args.append(f"--rtt-warn={thresholds['rtt'][0]}")
            args.append(f"--rtt-crit={thresholds['rtt'][1]}")
        
        if thresholds['jitter']:
            args.append(f"--jitter-warn={thresholds['jitter'][0]}")
            args.append(f"--jitter-crit={thresholds['jitter'][1]}")
        
        if thresholds['packet_loss']:
            args.append(f"--packet-loss-warn={thresholds['packet_loss'][0]}")
            args.append(f"--packet-loss-crit={thresholds['packet_loss'][1]}")
        
        if thresholds['fps']:
            args.append(f"--fps-warn={thresholds['fps'][0]}")
            args.append(f"--fps-crit={thresholds['fps'][1]}")
        
        if thresholds['bpp']:
            args.append(f"--bpp-warn={thresholds['bpp'][0]}")
            args.append(f"--bpp-crit={thresholds['bpp'][1]}")
        
        if thresholds['bitrate']:
            args.append(f"--bitrate-warn={thresholds['bitrate'][0]}")
            args.append(f"--bitrate-crit={thresholds['bitrate'][1]}")
        
        if thresholds['q_score']:
            args.append(f"--q-score-warn={thresholds['q_score'][0]}")
            args.append(f"--q-score-crit={thresholds['q_score'][1]}")
        
        yield ActiveCheckCommand(
            service_description=params.description,
            command_arguments=args
        )
    
    except Exception as e:
        raise

active_check_rtmp_ffmpeg_metrics = ActiveCheckConfig(
    name="rtmp_ffmpeg_metrics",
    parameter_parser=RtmpParams.model_validate,
    commands_function=generate_rtmp_services,
)
