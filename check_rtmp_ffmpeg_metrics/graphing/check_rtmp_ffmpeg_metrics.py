#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# Check RTMP ffmpeg metrics
# 2026/04/01- Graphing v1 for Check_MK 2.4 by swj67@protonmail.com - https://github.com/wjs67/check_mk_plugins

from cmk.graphing.v1 import graphs, Title
from cmk.graphing.v1.metrics import Metric, Unit, DecimalNotation, Color

# 1. Registro das métricas (conforme saem no seu Performance Data)
metric_rtmp_rtt = Metric(name="rtmp_rtt", 
        title=Title("RTT (Round Trip Time)"), 
        unit=Unit(notation=DecimalNotation(symbol='ms')),
        color=Color.DARK_BLUE,
)

metric_rtmp_jitter = Metric(name="rtmp_jitter", 
        title=Title("Jitter"), 
        unit=Unit(notation=DecimalNotation(symbol='ms')),
        color=Color.LIGHT_BLUE,
)

metric_rtmp_packet_loss = Metric(name="rtmp_packet_loss", 
        title=Title("Packet Loss"), 
        unit=Unit(notation=DecimalNotation(symbol='%')),
        color=Color.ORANGE,
)

metric_rtmp_fps = Metric(name="rtmp_fps", 
        title=Title("Frames Per Second(FPS)"), 
        unit=Unit(notation=DecimalNotation(symbol='')),
        color=Color.GREEN,
)

metric_rtmp_speed = Metric(name="rtmp_speed", 
        title=Title("Speed"), 
        unit=Unit(notation=DecimalNotation(symbol='x')),
        color=Color.DARK_GREEN,
)

metric_rtmp_bitrate = Metric(name="rtmp_bitrate", 
        title=Title("Bitrate: % bitrate_ideal"), 
        unit=Unit(notation=DecimalNotation(symbol='%')),
        color=Color.CYAN,
)

metric_rtmp_bpp = Metric(name="rtmp_bpp", 
        title=Title("Bits Per Pixel(BPP): % bpp_ideal"), 
        unit=Unit(notation=DecimalNotation(symbol='%')),
        color=Color.PURPLE,
)

metric_rtmp_q_score = Metric(name="rtmp_q_score", 
        title=Title("Q-Score"), 
        unit=Unit(notation=DecimalNotation(symbol='%')), 
        color=Color.DARK_YELLOW,
)

