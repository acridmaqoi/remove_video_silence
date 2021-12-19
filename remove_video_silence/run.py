import os
import sys
import logging
import re
import subprocess
import datetime
import glob
import shutil

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)


SILENCE_START_RE = re.compile(" silence_start: (?P<start>[0-9]+(\.?[0-9]*))$")
SILENCE_END_RE = re.compile(" silence_end: (?P<end>[0-9]+(\.?[0-9]*)) ")
TOTAL_DURATION_RE = re.compile(
    "size=[^ ]+ time=(?P<hours>[0-9]{2}):(?P<minutes>[0-9]{2}):(?P<seconds>[0-9\.]{5}) bitrate="
)


def execute_silent_detect(file):
    p = subprocess.Popen(
        [
            "ffmpeg",
            "-i",
            file,
            "-filter_complex",
            "[0]silencedetect=d=0.5:n=-50dB[s0]",
            "-map",
            "[s0]",
            "-f",
            "null",
            "-",
            "-nostats",
        ],
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


def remove_silence(chunks, video_name):
    # rm leftover files
    for f in glob.glob("tmp/*"):
        os.remove(f)

    try:
        os.mkdir("tmp")
    except FileExistsError:
        pass

    for i, (start_secs, end_secs) in enumerate(chunks):
        start_fmt = str(datetime.timedelta(seconds=start_secs)).split(".")[0]
        end_fmt = str(datetime.timedelta(seconds=end_secs)).split(".")[0]
        logger.info(f"splitting from {start_fmt} to {end_fmt}")

        duration = end_secs - start_secs
        filename = f"{i}.mp4"

        out_path = f"tmp/{filename}"

        subprocess.run(
            [
                "ffmpeg",
                "-ss",
                str(start_secs),
                "-i",
                video_name,
                "-y",
                "-filter_complex",
                "[0:a:0]amix=inputs=1[a];[a]aresample=async=1000[outa]",
                "-t",
                str(duration),
                "-crf",
                "15",
                "-ignore_unknown",
                "-max_muxing_queue_size",
                "9999",
                "-c:v",
                "h264_nvenc",
                "-preset",
                "fast",
                "-map",
                "0:v:0",
                "-map",
                "[outa]",
                out_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        with open("tmp/input.txt", "a") as f:
            f.write(f"file '{filename}'\n")

    logger.info("finalizing...")

    subprocess.run(
        [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            "tmp/input.txt",
            "-y",
            "-c",
            "copy",
            "result.mp4",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    shutil.rmtree("tmp")


def remove_video_silence(video: str):
    silence_output = execute_silent_detect(video)
    chunks = get_video_chunks(silence_output)
    remove_silence(chunks, video)


if __name__ == "__main__":
    video = sys.argv[1]
    remove_video_silence(video)
