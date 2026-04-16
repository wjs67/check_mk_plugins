#!/usr/bin/env python3

"""
RTMP Metrics Monitor
Monitors RTMP streams and collects quality metrics (RTT, Jitter, Packet Loss, FPS, BPP, Q-score)
2026/04/01- Rulesets v1 for Check_MK 2.4 by swj67@protonmail.com - https://github.com/wjs67/check_mk_plugins

REQUIREMENTS:
- FFmpeg: Required for capturing and analyzing RTMP streams
- ss (socket statistics): For network metrics (usually pre-installed with iproute2)
- Python 3.x

"""

import subprocess
import re
import sys
import time
from typing import Optional
import argparse


class RTMPRTTMonitor:
    def __init__(
        self,
        source_url: str,
        rtt_warn: Optional[float] = None,
        rtt_crit: Optional[float] = None,
        jitter_warn: Optional[float] = None,
        jitter_crit: Optional[float] = None,
        packet_loss_warn: Optional[float] = None,
        packet_loss_crit: Optional[float] = None,
        fps_warn: Optional[float] = None,
        fps_crit: Optional[float] = None,
        speed_warn: Optional[float] = None,
        speed_crit: Optional[float] = None,
        bpp_warn: Optional[float] = None,
        bpp_crit: Optional[float] = None,
        bitrate_warn: Optional[float] = None,
        bitrate_crit: Optional[float] = None,
        q_score_warn: Optional[float] = None,
        q_score_crit: Optional[float] = None,
    ):
        self.source_url = source_url
        self.host = self._extract_host(source_url)
        self.remote_port = self._extract_remote_port(source_url)
        self.sessions = []
        self.ffmpeg_process = None
        self.active_port_info = None  # Stores full connection info dict with PID
        self.last_grep_output = None  # Store output from last grep command
        self.fps_value = 0.0
        self.speed_value = 0.0
        self.bitrate_value = 0.0
        self.resolution = "N/A"
        self.display_width = None
        self.display_height = None
        self.rtt_jitter_data = {}
        self.bpp_real = 0.0
        self.bpp_ideal = 0.0
        self.bpp_percentage = 0.0
        self.bpp_ratio = 0.0
        self.bitrate_ideal = 0.0
        self.bitrate_percentage = 0.0
        self.bitrate_ratio = 0.0
        # Previous values for delta calculation (packet loss)
        self.last_retrans = 0
        self.last_segs_out = 0

        # Quality profiles: unified reference table (resolution, fps) -> {bpp_ideal, bitrate_ideal}
        # https://support.google.com/youtube/answer/2853702
        # BPP formula: (Mbps * 1,000,000) / (Width * Height * FPS)
        # Bitrate in kbps based on quality standards for different resolutions and frame rates
        self.quality_profiles = {
            (3840, 2160, 60): {'bpp': 0.050, 'bitrate': 25000},   # 4K Ultra HD Premium
            (3840, 2160, 30): {'bpp': 0.080, 'bitrate': 20000},   # 4K Cinema / High Fidelity
            (2560, 1440, 60): {'bpp': 0.065, 'bitrate': 14500},   # 2K / QHD Gaming
            (2560, 1440, 30): {'bpp': 0.100, 'bitrate': 11000},   # 2K High Quality
            (1920, 1080, 60): {'bpp': 0.070, 'bitrate': 8700},    # Full HD 60fps (Twitch/YT Standard)
            (1920, 1080, 30): {'bpp': 0.100, 'bitrate': 6200},    # Full HD 30fps (Netflix Standard)
            (1280, 720, 60):  {'bpp': 0.090, 'bitrate': 5000},    # HD High Motion
            (1280, 720, 30):  {'bpp': 0.130, 'bitrate': 3600},    # HD Standard (Ideal)
            (640, 360, 30):   {'bpp': 0.180, 'bitrate': 1250},    # Mobile / Low Bandwidth
            (426, 240, 30):   {'bpp': 0.220, 'bitrate': 675}      # Emergency / Very Low Link
        }

        # Define RTT thresholds (milliseconds)
        self.rtt_thresholds = {
            'ok': 5,
            'warning': rtt_warn if rtt_warn is not None else 5,
            'critical': rtt_crit if rtt_crit is not None else 20
        }

        # Define Jitter thresholds (milliseconds)
        self.jitter_thresholds = {
            'ok': 2,
            'warning': jitter_warn if jitter_warn is not None else 10,
            'critical': jitter_crit if jitter_crit is not None else 30
        }

        # Define Packet Loss thresholds (percentage)
        self.packet_loss_thresholds = {
            'ok': 0.0,
            'warning': packet_loss_warn if packet_loss_warn is not None else 0.5,
            'critical': packet_loss_crit if packet_loss_crit is not None else 2.0
        }

        # Define FPS thresholds
        self.fps_thresholds = {
            'ok_min': 29,
            'ok_max': 30,
            'warning': fps_warn if fps_warn is not None else 27,
            'critical': fps_crit if fps_crit is not None else 24
        }

        # Define SPEED thresholds
        self.speed_thresholds = {
            'ok': 0.95,
            'warning': speed_warn if speed_warn is not None else 999999.0,
            'critical': speed_crit if speed_crit is not None else 999999.0
        }

        # Define BPP thresholds (percentage)
        self.bpp_thresholds = {
            'warning': bpp_warn if bpp_warn is not None else 80.0,
            'critical': bpp_crit if bpp_crit is not None else 60.0
        }

        # Define Bitrate thresholds (percentage)
        self.bitrate_thresholds = {
            'warning': bitrate_warn if bitrate_warn is not None else 70.0,
            'critical': bitrate_crit if bitrate_crit is not None else 50.0
        }

        # Define Q-Score thresholds
        self.q_score_thresholds = {
            'warning': q_score_warn if q_score_warn is not None else 85,
            'critical': q_score_crit if q_score_crit is not None else 70
        }

        # Q-score target values
        self.fps_target = 30
        self.q_score = 0.0


    def _extract_host(self, url: str) -> Optional[str]:
        """Extracts hostname from RTMP URL"""
        try:
            # rtmp://10.0.0.1/... -> 10.0.0.1
            match = re.search(r'rtmp[s]?://([^/:]+)', url)
            if match:
                return match.group(1)
        except:
            pass
        return None

    def _extract_remote_port(self, url: str) -> int:
        """Extracts remote port from RTMP URL (defaults to 1935 for RTMP, 443 for RTMPS)"""
        try:
            # rtmp://10.0.0.1:19350/... -> 19350
            match = re.search(r'rtmp[s]?://[^/:]+:(\d+)', url)
            if match:
                return int(match.group(1))
        except:
            pass
        # Return default port based on protocol
        return 443 if 'rtmps' in url else 1935

    def _get_active_port_info(self) -> Optional[dict]:
        """
        Finds the local port used by the FFmpeg process to connect to the remote RTMP host.
        Returns a dict with: {local_port, local_ip, remote_ip, remote_port, ffmpeg_pid}
        Uses process PID for accurate matching in multi-session scenarios.
        """
        if not self.host or not self.ffmpeg_process or not self.ffmpeg_process.pid:
            return None

        try:
            remote_port = self.remote_port
            ffmpeg_pid = self.ffmpeg_process.pid

            # Option 1: Use lsof to get connections for specific FFmpeg PID (most reliable)
            try:
                result = subprocess.run(
                    ['lsof', '-p', str(ffmpeg_pid), '-a', '-iTCP', '-sTCP:ESTABLISHED'],
                    capture_output=True, text=True, timeout=3
                )

                if result.returncode == 0 and result.stdout:
                    for line in result.stdout.split('\n')[1:]:  # Skip header
                        if 'ESTABLISHED' in line and self.host in line:
                            parts = line.split()
                            if len(parts) >= 9:
                                conn_info = parts[8]
                                if '->' in conn_info:
                                    local_part, remote_part = conn_info.split('->')
                                    if ':' in local_part and ':' in remote_part:
                                        local_ip, local_port = local_part.rsplit(':', 1)
                                        remote_ip, remote_port_str = remote_part.rsplit(':', 1)

                                        if remote_ip == self.host:
                                            return {
                                                'local_port': local_port,
                                                'local_ip': local_ip.strip('()[]'),
                                                'remote_ip': remote_ip,
                                                'remote_port': int(remote_port_str),
                                                'ffmpeg_pid': ffmpeg_pid
                                            }
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

            # Option 2: Fallback - Use ss with filtering by destination host and port
            try:
                result = subprocess.run(
                    ['ss', '-ti', 'dst', f'{self.host}:{remote_port}'],
                    capture_output=True, text=True, timeout=5
                )

                if result.returncode == 0:
                    output = result.stdout
                    lines = output.split('\n')

                    for line in lines:
                        if 'ESTAB' in line:
                            m_local = re.search(r'(\d+\.\d+\.\d+\.\d+):(\d+)', line)
                            if m_local:
                                return {
                                    'local_port': m_local.group(2),
                                    'local_ip': m_local.group(1),
                                    'remote_ip': self.host,
                                    'remote_port': remote_port,
                                    'ffmpeg_pid': ffmpeg_pid
                                }
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        except Exception as e:
            pass

        return None

    def _stop_ffmpeg(self) -> None:
        """Stops the ffmpeg process"""
        if self.ffmpeg_process:
            self.ffmpeg_process.terminate()
            try:
                self.ffmpeg_process.wait(timeout=2)
            except:
                self.ffmpeg_process.kill()

    def _capture_metrics_parallel(self) -> None:
        """Captures FPS/SPEED/Resolution via FFmpeg and RTT/Jitter via ss from the SAME connection"""
        try:
            # Start single FFmpeg connection (10 seconds) - production-like scenario with copy codec
            cmd_str = f"ffmpeg -nostdin -rtmp_live live -i {self.source_url} -t 10 -c copy -f mpegts /dev/null -y 2>&1"

            self.ffmpeg_process = subprocess.Popen(
                cmd_str,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            # Give FFmpeg time to establish connection
            time.sleep(0.5)

            # Store FFmpeg PID immediately (before any operations that might fail)
            if self.ffmpeg_process and self.ffmpeg_process.pid:
                self.rtt_jitter_data['ffmpeg_pid'] = self.ffmpeg_process.pid

            # Get active port info from the FFmpeg connection (with PID-based matching)
            self.active_port_info = self._get_active_port_info()

            if self.active_port_info:
                # Store connection info in rtt_jitter_data immediately
                self.rtt_jitter_data['local_ip'] = self.active_port_info['local_ip']
                self.rtt_jitter_data['local_port'] = self.active_port_info['local_port']
                self.rtt_jitter_data['remote_ip'] = self.active_port_info['remote_ip']
                self.rtt_jitter_data['remote_port'] = self.active_port_info['remote_port']

                # Capture RTT/Jitter while FFmpeg is running (reads from established connection)
                self._capture_rtt_jitter_from_active_connection()

            # Wait for FFmpeg to complete and capture FPS/SPEED/Resolution
            try:
                output, _ = self.ffmpeg_process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                self.ffmpeg_process.kill()
                try:
                    output, _ = self.ffmpeg_process.communicate(timeout=5)
                except:
                    output = ""

            # Extract resolution, fps from displayWidth/displayHeight and fps metadata
            self.display_width = None
            self.display_height = None
            fps_from_metadata = 0.0

            for line in output.split('\n'):
                if 'displayWidth' in line:
                    width_match = re.search(r'displayWidth\s*:\s*(\d+)', line)
                    if width_match:
                        self.display_width = int(width_match.group(1))
                elif 'displayHeight' in line:
                    height_match = re.search(r'displayHeight\s*:\s*(\d+)', line)
                    if height_match:
                        self.display_height = int(height_match.group(1))
                elif 'fps' in line and ':' in line and not fps_from_metadata:
                    fps_match = re.search(r'fps\s*:\s*(\d+(?:\.\d+)?)', line)
                    if fps_match:
                        try:
                            fps_from_metadata = float(fps_match.group(1))
                        except:
                            pass

            # Build resolution string from displayWidth and displayHeight
            if self.display_width and self.display_height:
                self.resolution = f"{self.display_width}x{self.display_height}"

            # Extract FPS and SPEED - Try frame= lines first, then progress lines
            frame_lines = [line for line in output.split('\n') if 'frame=' in line]
            progress_lines = [line for line in output.split('\n') if 'speed=' in line and 'bitrate=' in line]

            # Use frame lines if available, otherwise use progress lines
            lines = frame_lines if frame_lines else progress_lines

            if lines:
                last_line = lines[-1]

                # Extract FPS (frame count / 10 seconds) - if frame= exists
                if frame_lines:
                    frame_match = re.search(r'frame=\s*(\d+)', last_line)
                    if frame_match:
                        try:
                            frame_count = int(frame_match.group(1))
                            self.fps_value = frame_count / 10.0
                        except:
                            pass

                # If no FPS from frame count, use metadata value
                if self.fps_value == 0.0 and fps_from_metadata > 0:
                    self.fps_value = fps_from_metadata

                # Extract SPEED
                speed_match = re.search(r'speed=\s*([\d.]+)x', last_line)
                if speed_match:
                    try:
                        self.speed_value = float(speed_match.group(1))
                    except:
                        pass

                # Extract Bitrate (kbits/s)
                bitrate_match = re.search(r'bitrate=\s*([\d.]+)kbits', last_line)
                if bitrate_match:
                    try:
                        self.bitrate_value = float(bitrate_match.group(1))
                    except:
                        pass

                # If no bitrate found in progress line, try to find it in codec line
                if self.bitrate_value == 0.0:
                    for line in output.split('\n'):
                        if 'Stream #0' in line and 'kbits' in line:
                            br_match = re.search(r'(\d+)\s*kb/s', line)
                            if br_match:
                                try:
                                    self.bitrate_value = float(br_match.group(1))
                                    break
                                except:
                                    pass

        except Exception as e:
            pass
        finally:
            self._stop_ffmpeg()

    def _capture_rtt_jitter_from_active_connection(self) -> None:
        """
        Captures RTT, Jitter and Packet Loss from the active FFmpeg connection via ss.
        Uses IP + port matching to ensure correct connection is identified,
        even with multiple simultaneous RTMP sessions to the same server.
        """
        try:
            if not self.active_port_info:
                return

            local_port = self.active_port_info['local_port']
            local_ip = self.active_port_info['local_ip']
            remote_ip = self.active_port_info['remote_ip']
            remote_port = self.active_port_info['remote_port']

            # Read ss stats filtering by remote IP and port for precise matching
            try:
                result = subprocess.run(
                    ['ss', '-ti', 'dst', f'{remote_ip}:{remote_port}'],
                    capture_output=True, text=True, timeout=5
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                # Fallback: if destination filtering fails, try generic dst
                try:
                    result = subprocess.run(
                        ['ss', '-ti', 'dst', remote_ip],
                        capture_output=True, text=True, timeout=5
                    )
                except:
                    return

            if result.returncode == 0:
                output = result.stdout
                lines = output.split('\n')

                # Process line pairs and find stats for active connection
                for i in range(len(lines) - 1):
                    line = lines[i]
                    next_line = lines[i + 1]

                    # Check for ESTAB connection
                    if 'ESTAB' in line:
                        m_local = re.search(r'(\d+\.\d+\.\d+\.\d+|\[.*?\]):(\d+)', line)

                        if m_local and m_local.group(2) == local_port:
                            # Extract RTT and Jitter from stats line
                            m_rtt = re.search(r'rtt:(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)', next_line)

                            if m_rtt:
                                self.rtt_jitter_data['rtt'] = float(m_rtt.group(1))
                                self.rtt_jitter_data['jitter'] = float(m_rtt.group(2))

                                # Extract packet loss metrics
                                m_retrans = re.search(r'retrans:(\d+)', next_line)
                                m_segs_out = re.search(r'segs_out:(\d+)', next_line)
                                current_retrans = int(m_retrans.group(1)) if m_retrans else 0
                                current_segs_out = int(m_segs_out.group(1)) if m_segs_out else 0

                                # Calculate delta (difference from last capture)
                                delta_retrans = current_retrans - self.last_retrans
                                delta_segs_out = current_segs_out - self.last_segs_out

                                # Protect against negative deltas
                                delta_retrans = max(0, delta_retrans)
                                delta_segs_out = max(0, delta_segs_out)

                                # Calculate packet loss percentage
                                if self.last_retrans == 0 and self.last_segs_out == 0:
                                    packet_loss_pct = 0.0
                                elif delta_segs_out > 0:
                                    packet_loss_pct = (delta_retrans / delta_segs_out) * 100
                                else:
                                    packet_loss_pct = 0.0

                                # Store current values
                                self.last_retrans = current_retrans
                                self.last_segs_out = current_segs_out

                                self.rtt_jitter_data['retrans'] = current_retrans
                                self.rtt_jitter_data['segs_out'] = current_segs_out
                                self.rtt_jitter_data['packet_loss'] = packet_loss_pct
                                break
        except Exception as e:
            pass


    def collect(self) -> None:
        """Collects all metrics (FPS, SPEED, Resolution, RTT, Jitter, Packet Loss) from a SINGLE FFmpeg connection"""
        if not self.host:
            print("Error: Could not extract host from RTMP URL")
            return

        try:
            # Capture all metrics from single FFmpeg connection
            self._capture_metrics_parallel()

            # Validate if stream is accessible
            if self.fps_value == 0.0 and self.speed_value == 0.0:
                print(f"Error: Could not connect to RTMP stream {self.source_url} or stream does not exist")
                sys.exit(2)

            if self.resolution == "N/A":
                print(f"Error: Could not retrieve video resolution from {self.source_url}")
                sys.exit(2)

            # Check if RTT/Jitter data was captured
            if not self.rtt_jitter_data:
                print("Error: Could not capture RTT/Jitter statistics")
                sys.exit(2)

            # Calculate BPP metrics
            self.bpp_real = self._calculate_bpp_real(self.bitrate_value, self.display_width, self.display_height, self.fps_value)
            self.bpp_ideal = self._get_bpp_ideal(self.display_width, self.display_height, self.fps_value)
            if self.bpp_ideal and self.bpp_ideal > 0:
                # Percentage variation: positive means higher than ideal (worse), negative means lower than ideal (better)
                self.bpp_percentage = ((self.bpp_real - self.bpp_ideal) / self.bpp_ideal) * 100
                # BPP ratio: BPP real as percentage of BPP ideal (0-100%)
                self.bpp_ratio = (self.bpp_real / self.bpp_ideal) * 100

            # Calculate Bitrate metrics
            self.bitrate_ideal = self._get_bitrate_ideal(self.display_width, self.display_height, self.fps_value)
            if self.bitrate_ideal and self.bitrate_ideal > 0:
                # Bitrate ratio: bitrate_value as percentage of bitrate_ideal (0-100%)
                self.bitrate_ratio = (self.bitrate_value / self.bitrate_ideal) * 100
                # Percentage variation
                self.bitrate_percentage = ((self.bitrate_value - self.bitrate_ideal) / self.bitrate_ideal) * 100

            # Calculate Q-score
            if self.bpp_ideal and self.bpp_ideal > 0:
                # Use actual FPS from stream as target (or default to 30 if not detected)
                fps_target = self.fps_value if self.fps_value > 0 else self.fps_target
                self.q_score = self.calculate_q_score(self.fps_value, fps_target, self.bpp_real, self.bpp_ideal)

            # Build session data from captured values
            self.sessions.append({
                'port': self.rtt_jitter_data.get('local_port', 'N/A'),
                'local_ip': self.rtt_jitter_data.get('local_ip', 'N/A'),
                'rtt': self.rtt_jitter_data.get('rtt', 0.0),
                'jitter': self.rtt_jitter_data.get('jitter', 0.0),
                'retrans': self.rtt_jitter_data.get('retrans', 0),
                'segs_out': self.rtt_jitter_data.get('segs_out', 1),
                'packet_loss': self.rtt_jitter_data.get('packet_loss', 0.0),
                'fps': self.fps_value,
                'bitrate': self.bitrate_value,
                'speed': self.speed_value,
                'resolution': self.resolution,
                'bpp_real': self.bpp_real,
                'bpp_ideal': self.bpp_ideal,
                'bpp_percentage': self.bpp_percentage,
                'bpp_ratio': self.bpp_ratio,
                'bitrate_ideal': self.bitrate_ideal,
                'bitrate_percentage': self.bitrate_percentage,
                'bitrate_ratio': self.bitrate_ratio,
                'q_score': self.q_score,
                'ffmpeg_pid': self.rtt_jitter_data.get('ffmpeg_pid', None)
            })
        except Exception as e:
            print(f"Error collecting metrics: {e}")

    def calculate_q_score(self, fps_real: float, fps_target: float, bpp_real: float, bpp_ideal: float) -> float:
        """Calculates Q-score based on FPS and BPP metrics
        - 40% weight for fluidity (FPS)
        - 60% weight for sharpness (BPP)
        - Result is capped at 100
        """
        if fps_target == 0 or bpp_ideal == 0:
            return 0.0

        score_fps = (fps_real / fps_target) * 100
        score_bpp = (bpp_real / bpp_ideal) * 100

        q_score = (score_fps * 0.4) + (score_bpp * 0.6)
        return min(100, q_score)

    def _get_bpp_ideal(self, width: Optional[int], height: Optional[int], fps: float) -> Optional[float]:
        """Gets BPP ideal value from quality profiles, finding closest FPS match"""
        if not width or not height or fps == 0:
            return None

        # Find entries matching resolution
        matching_entries = [(f, profile['bpp']) for (w, h, f), profile in self.quality_profiles.items() if w == width and h == height]

        if not matching_entries:
            return None

        # Return BPP for closest FPS match
        closest = min(matching_entries, key=lambda x: abs(x[0] - fps))
        return closest[1]

    def _calculate_bpp_real(self, bitrate_kbps: float, width: Optional[int], height: Optional[int], fps: float) -> float:
        """Calculates BPP real: (Mbps * 1,000,000) / (Width * Height * FPS)"""
        if not width or not height or fps == 0:
            return 0.0

        bitrate_bps = bitrate_kbps * 1000  # Convert kbps to bps
        bpp = bitrate_bps / (width * height * fps)
        return bpp

    def _get_bitrate_ideal(self, width: Optional[int], height: Optional[int], fps: float) -> Optional[float]:
        """Gets bitrate ideal value from quality profiles, finding closest FPS match
        Returns bitrate in kbps
        """
        if not width or not height or fps == 0:
            return None

        # Find entries matching resolution
        matching_entries = [(f, profile['bitrate']) for (w, h, f), profile in self.quality_profiles.items() if w == width and h == height]

        if not matching_entries:
            return None

        # Return bitrate for closest FPS match
        closest = min(matching_entries, key=lambda x: abs(x[0] - fps))
        return closest[1]

    def _get_bitrate_status(self, bitrate_ratio: float) -> tuple:
        """Evaluates Bitrate status based on efficiency (bitrate / bitrate_ideal * 100)
        Returns: (status_code, status_name, message)

        Thresholds > 1000 are treated as 'disabled' (no alert)
        """
        efficiency = bitrate_ratio  # bitrate_ratio is already a percentage
        crit_threshold = self.bitrate_thresholds['critical']
        warn_threshold = self.bitrate_thresholds['warning']

        # If critical threshold is very high (>1000), treat as disabled
        if crit_threshold > 1000:
            return (0, 'OK', f"[OK] Bitrate: {efficiency:.2f}%")

        # Critical: below critical threshold
        if efficiency < crit_threshold:
            return (2, 'CRIT', f"[CRIT] Bitrate too low: {efficiency:.2f}% (Poor quality)")

        # Warning: below warning threshold (only if not disabled)
        if warn_threshold <= 1000 and efficiency < warn_threshold:
            return (1, 'WARN', f"[WARN] Bitrate low: {efficiency:.2f}% (Quality compromised)")

        # OK - Bitrate above warning threshold
        return (0, 'OK', f"[OK] Bitrate: {efficiency:.2f}%")

    def _get_bpp_status(self, bpp_ratio: float) -> tuple:
        """Evaluates BPP status based on efficiency (bpp_real / bpp_ideal * 100)
        Returns: (status_code, status_name, message)

        Thresholds > 1000 are treated as 'disabled' (no alert)
        """
        efficiency = bpp_ratio  # bpp_ratio is already a percentage
        crit_threshold = self.bpp_thresholds['critical']
        warn_threshold = self.bpp_thresholds['warning']

        # If critical threshold is very high (>1000), treat as disabled
        if crit_threshold > 1000:
            return (0, 'OK', f"[OK] BPP: {efficiency:.2f}%")

        # Critical: below critical threshold
        if efficiency < crit_threshold:
            return (2, 'CRIT', f"[CRIT] BPP too low: {efficiency:.2f}% (Poor image quality)")

        # Warning: below warning threshold (only if not disabled)
        if warn_threshold <= 1000 and efficiency < warn_threshold:
            return (1, 'WARN', f"[WARN] BPP low: {efficiency:.2f}% (Below optimal)")

        # OK - BPP above warning threshold
        return (0, 'OK', f"[OK] BPP: {efficiency:.2f}%")

    def _get_fps_status(self, fps: float) -> tuple:
        """Evaluates FPS status
        Returns: (status_code, status_name, message)

        Thresholds > 1000 are treated as 'disabled' (no alert)
        """
        crit_threshold = self.fps_thresholds['critical']
        warn_threshold = self.fps_thresholds['warning']
        ok_min = self.fps_thresholds['ok_min']
        ok_max = self.fps_thresholds['ok_max']

        # If critical threshold is very high (>1000), treat as disabled
        if crit_threshold > 1000:
            return (0, 'OK', f"[OK] FPS: {fps:.2f}")

        # Critical: below critical threshold
        if fps < crit_threshold:
            return (2, 'CRIT', f"[CRIT] FPS too low: {fps:.2f}")

        # Warning: below warning threshold (only if not disabled)
        if warn_threshold <= 1000 and fps < warn_threshold:
            return (1, 'WARN', f"[WARN] FPS low: {fps:.2f}")

        # Check if within OK range
        if ok_min <= fps <= ok_max:
            return (0, 'OK', f"[OK] FPS: {fps:.2f}")

        # FPS above OK range (e.g., > 30)
        return (1, 'WARN', f"[WARN] FPS above optimal: {fps:.2f}")

    def _get_speed_status(self, speed: float) -> tuple:
        """Evaluates Speed status
        Returns: (status_code, status_name, message)

        Thresholds > 1000 are treated as 'disabled' (no alert)
        """
        crit_threshold = self.speed_thresholds['critical']
        warn_threshold = self.speed_thresholds['warning']

        # If critical threshold is very high (>1000), treat as disabled
        if crit_threshold > 1000:
            return (0, 'OK', f"[OK] Speed: {speed:.2f}x")

        # Critical: below critical threshold
        if speed < crit_threshold:
            return (2, 'CRIT', f"[CRIT] Speed too low: {speed:.2f}x")

        # Warning: below warning threshold (only if not disabled)
        if warn_threshold <= 1000 and speed < warn_threshold:
            return (1, 'WARN', f"[WARN] Speed low: {speed:.2f}x")

        # OK - Speed above warning threshold
        return (0, 'OK', f"[OK] Speed: {speed:.2f}x")

    def print_report(self) -> int:
        """Displays report in Nagios/Icinga format with summary and performance data
        Returns the exit status code
        """
        if not self.sessions:
            print('No active session found for this URL |')
            return 2   # ERROR alert

        session = self.sessions[0]
        rtt = session['rtt']
        jitter = session['jitter']
        packet_loss = session['packet_loss']
        fps = session['fps']
        bitrate = session['bitrate']
        speed = session['speed']
        resolution = session['resolution']
        bpp_real = session['bpp_real']
        bpp_ideal = session['bpp_ideal']
        bpp_ratio = session['bpp_ratio']
        bitrate = session['bitrate']
        bitrate_ideal = session['bitrate_ideal']
        bitrate_ratio = session['bitrate_ratio']
        q_score = session['q_score']

        # Initialize status and details list
        status_final = 0
        details = []

        # RTT Check
        if rtt > self.rtt_thresholds['critical']:
            status_final = max(status_final, 2)
            details.append(f"RTT: {rtt:.2f}ms(!!)")
        elif rtt > self.rtt_thresholds['warning']:
            status_final = max(status_final, 1)
            details.append(f"RTT: {rtt:.2f}ms(!)")
        else:
            details.append(f"RTT: {rtt:.2f}ms")

        # Jitter Check
        if jitter > self.jitter_thresholds['critical']:
            status_final = max(status_final, 2)
            details.append(f"Jitter: {jitter:.2f}ms(!!)")
        elif jitter > self.jitter_thresholds['warning']:
            status_final = max(status_final, 1)
            details.append(f"Jitter: {jitter:.2f}ms(!)")
        else:
            details.append(f"Jitter: {jitter:.2f}ms")

        # Packet Loss Check
        if packet_loss > self.packet_loss_thresholds['critical']:
            status_final = max(status_final, 2)
            details.append(f"Packet Loss: {packet_loss:.2f}%(!!)")
        elif packet_loss > self.packet_loss_thresholds['warning']:
            status_final = max(status_final, 1)
            details.append(f"Packet Loss: {packet_loss:.2f}%(!)")
        else:
            details.append(f"Packet Loss: {packet_loss:.2f}%")

        # FPS Check
        fps_status_code, fps_status, fps_msg = self._get_fps_status(fps)
        status_final = max(status_final, fps_status_code)
        status_suffix = ("(!!)" if fps_status_code == 2 else "(!)" if fps_status_code == 1 else "")
        details.append(f"FPS: {fps:.2f}{status_suffix}")

        # SPEED Check
        speed_status_code, speed_status, speed_msg = self._get_speed_status(speed)
        status_final = max(status_final, speed_status_code)
        status_suffix = ("(!!)" if speed_status_code == 2 else "(!)" if speed_status_code == 1 else "")
        details.append(f"SPEED: {speed:.2f}x{status_suffix}")

        # Bitrate Check (if available)
        if bitrate_ideal:
            bitrate_status_code, bitrate_status, bitrate_msg = self._get_bitrate_status(bitrate_ratio)
            status_final = max(status_final, bitrate_status_code)
            status_suffix = ("(!!)" if bitrate_status_code == 2 else "(!)" if bitrate_status_code == 1 else "")
            details.append(f"Bitrate: {bitrate_ratio:.2f}%{status_suffix}")

        # BPP Check (if available)
        if bpp_ideal:
            bpp_status_code, bpp_status, bpp_msg = self._get_bpp_status(bpp_ratio)
            status_final = max(status_final, bpp_status_code)
            status_suffix = ("(!!)" if bpp_status_code == 2 else "(!)" if bpp_status_code == 1 else "")
            details.append(f"BPP: {bpp_ratio:.2f}%{status_suffix}")

            # Q-Score Check
            q_score_crit = self.q_score_thresholds['critical']
            q_score_warn = self.q_score_thresholds['warning']

            # If critical threshold is very high (>1000), treat as disabled
            if q_score_crit > 1000:
                details.append(f"Q-score: {q_score:.2f}")
            elif q_score < q_score_crit:
                status_final = max(status_final, 2)
                details.append(f"Q-score: {q_score:.2f}(!!)")
            elif q_score_warn <= 1000 and q_score < q_score_warn:
                status_final = max(status_final, 1)
                details.append(f"Q-score: {q_score:.2f}(!)")
            else:
                details.append(f"Q-score: {q_score:.2f}")

        # Build summary message
        summary = " • ".join(details)

        # Build performance data (metrics) string
        metrics_parts = []
        metrics_parts.append(f"rtmp_rtt={rtt:.2f};{self.rtt_thresholds['warning']};{self.rtt_thresholds['critical']}")
        metrics_parts.append(f"rtmp_jitter={jitter:.2f};{self.jitter_thresholds['warning']};{self.jitter_thresholds['critical']}")
        metrics_parts.append(f"rtmp_packet_loss={packet_loss:.2f};{self.packet_loss_thresholds['warning']};{self.packet_loss_thresholds['critical']}")
        metrics_parts.append(f"rtmp_fps={fps:.2f};{self.fps_thresholds['warning']};{self.fps_thresholds['critical']}")
        metrics_parts.append(f"rtmp_speed={speed:.2f};{self.speed_thresholds['warning']};{self.speed_thresholds['critical']}")

        if bitrate_ideal:
            metrics_parts.append(f"rtmp_bitrate={bitrate_ratio:.2f};{self.bitrate_thresholds['warning']};{self.bitrate_thresholds['critical']}")

        if bpp_ideal:
            metrics_parts.append(f"rtmp_bpp={bpp_ratio:.2f};{self.bpp_thresholds['warning']};{self.bpp_thresholds['critical']}")
            metrics_parts.append(f"rtmp_q_score={q_score:.2f};{self.q_score_thresholds['warning']};{self.q_score_thresholds['critical']}")

        metrics = " ".join(metrics_parts)

        # Build details with ideal and measured values
        details_parts = [
            f"bpp_real={bpp_real:.6f}",
            f"bpp_ideal={bpp_ideal:.6f}",
            f"bitrate={bitrate:.2f}kbps",
            f"bitrate_ideal={bitrate_ideal:.2f}kbps",
            f"Resolution: {resolution}"
        ]

        # Add session PID for traceability in multi-session scenarios
        if 'ffmpeg_pid' in session and session['ffmpeg_pid']:
            details_parts.append(f"Session: {session['ffmpeg_pid']}")

        metrics_details = " • ".join(details_parts)

        # Sanitize output to ensure single-line format for Checkmk graphing
        # Remove any newline characters that may exist in summary or metrics_details
        summary = summary.replace('\n', ' ').strip()
        metrics_details = metrics_details.replace('\n', ' ').strip()
        metrics = metrics.replace('\n', ' ').strip()

        # Print in Nagios/Icinga format with performance data (ALL on ONE line)
        print(f'{summary}\n{metrics_details} | {metrics}')

        # Return status code for sys.exit()
        return status_final


def main():
    parser = argparse.ArgumentParser(
        description='RTMP Metrics Monitor - Monitor RTMP streams and collect quality metrics',
        epilog='Example: %(prog)s rtmp://10.0.0.10:1935/stream1/manifest --jitter-warn 15 --jitter-crit 35'
    )

    parser.add_argument('rtmp_url', help='RTMP stream URL')
    parser.add_argument('--rtt-warn', type=float, help='RTT warning threshold (ms)')
    parser.add_argument('--rtt-crit', type=float, help='RTT critical threshold (ms)')
    parser.add_argument('--jitter-warn', type=float, help='Jitter warning threshold (ms)')
    parser.add_argument('--jitter-crit', type=float, help='Jitter critical threshold (ms)')
    parser.add_argument('--packet-loss-warn', type=float, help='Packet loss warning threshold (%)')
    parser.add_argument('--packet-loss-crit', type=float, help='Packet loss critical threshold (%)')
    parser.add_argument('--fps-warn', type=float, help='FPS warning threshold')
    parser.add_argument('--fps-crit', type=float, help='FPS critical threshold')
    parser.add_argument('--speed-warn', type=float, help='Speed warning threshold')
    parser.add_argument('--speed-crit', type=float, help='Speed critical threshold')
    parser.add_argument('--bpp-warn', type=float, help='BPP warning threshold (%)')
    parser.add_argument('--bpp-crit', type=float, help='BPP critical threshold (%)')
    parser.add_argument('--bitrate-warn', type=float, help='Bitrate warning threshold (%)')
    parser.add_argument('--bitrate-crit', type=float, help='Bitrate critical threshold (%)')
    parser.add_argument('--q-score-warn', type=float, help='Q-Score warning threshold')
    parser.add_argument('--q-score-crit', type=float, help='Q-Score critical threshold')

    args = parser.parse_args()

    monitor = RTMPRTTMonitor(
        source_url=args.rtmp_url,
        rtt_warn=args.rtt_warn,
        rtt_crit=args.rtt_crit,
        jitter_warn=args.jitter_warn,
        jitter_crit=args.jitter_crit,
        packet_loss_warn=args.packet_loss_warn,
        packet_loss_crit=args.packet_loss_crit,
        fps_warn=args.fps_warn,
        fps_crit=args.fps_crit,
        speed_warn=args.speed_warn,
        speed_crit=args.speed_crit,
        bpp_warn=args.bpp_warn,
        bpp_crit=args.bpp_crit,
        bitrate_warn=args.bitrate_warn,
        bitrate_crit=args.bitrate_crit,
        q_score_warn=args.q_score_warn,
        q_score_crit=args.q_score_crit,
    )
    monitor.collect()
    status_code = monitor.print_report()
    sys.exit(status_code)


if __name__ == "__main__":
    main()


