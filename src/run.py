import sys
import logging
import re
import subprocess

import ffmpeg

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)


in_file = ffmpeg.input("input.mp4")


def run_ffmpeg_cmd(cmd_line, *args, **kwargs):
    logger.debug("Running command: {}".format(subprocess.list2cmdline(cmd_line)))
    return subprocess.Popen(cmd_line, *args, **kwargs)


SILENCE_START_RE = re.compile(" silence_start: (?P<start>[0-9]+(\.?[0-9]*))$")
SILENCE_END_RE = re.compile(" silence_end: (?P<end>[0-9]+(\.?[0-9]*)) ")
TOTAL_DURATION_RE = re.compile(
    "size=[^ ]+ time=(?P<hours>[0-9]{2}):(?P<minutes>[0-9]{2}):(?P<seconds>[0-9\.]{5}) bitrate="
)


def get_video_silence(cls, file):
    return cls.__parse_silence_output(cls.__execute_silent_detect(file))


def execute_silent_detect(file):
    p = run_ffmpeg_cmd(
        (
            ffmpeg.input(file)
            .filter("silencedetect", n="-50dB", d="5")
            .output("-", format="null")
            .compile()
            + ["-nostats"]
        ),
        stderr=subprocess.PIPE,
    )
    output = p.communicate()[1].decode("utf-8")

    if p.returncode != 0:
        sys.stderr.write(output)
        sys.exit(1)
    logger.debug(output)

    return output


def get_video_chunks(output):
    start_time = 0  # TODO
    end_time = None

    lines = output.splitlines()
    # Chunks start when silence ends, and chunks end when silence starts.
    chunk_starts = []
    chunk_ends = []
    for line in lines:
        silence_start_match = SILENCE_START_RE.search(line)
        silence_end_match = SILENCE_END_RE.search(line)
        total_duration_match = TOTAL_DURATION_RE.search(line)
        if silence_start_match:
            chunk_ends.append(float(silence_start_match.group("start")))
            if len(chunk_starts) == 0:
                # Started with non-silence.
                chunk_starts.append(start_time or 0.0)
        elif silence_end_match:
            chunk_starts.append(float(silence_end_match.group("end")))
        elif total_duration_match:
            hours = int(total_duration_match.group("hours"))
            minutes = int(total_duration_match.group("minutes"))
            seconds = float(total_duration_match.group("seconds"))
            end_time = hours * 3600 + minutes * 60 + seconds

    if len(chunk_starts) == 0:
        # No silence found.
        chunk_starts.append(start_time)

    if len(chunk_starts) > len(chunk_ends):
        # Finished with non-silence.
        chunk_ends.append(end_time or 10000000.0)

    return list(zip(chunk_starts, chunk_ends))


def remove_silence(chunks, video):
    in_file = ffmpeg.input(video)
    ffmpeg.filter
    video_chunks = [
        in_file.filter("trim", start=start, end=end) for (start, end) in chunks
    ]
    audio_chunks = [
        in_file.filter("atrim", start=start, end=end) for (start, end) in chunks
    ]

    output = ffmpeg.concat(a1, v1, v=1, a=1).output(
        f"test-crop.mp4", vcodec="h264_nvenc"
    )
    run_ffmpeg_cmd(output.compile())


if __name__ == "__main__":
    video = "input.mp4"
    silence_output = execute_silent_detect(video)
    chunks = get_video_chunks(silence_output)

    remove_silence(chunks, video)
