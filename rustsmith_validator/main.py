import argparse
import concurrent.futures
import os
import shutil
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from threading import current_thread
from typing import Dict

import typer
from click._termui_impl import ProgressBar, V

from rustsmith_validator.config import config


def compile_and_run(
    file_path: Path,
    entry: (str, str),
    progress: ProgressBar[V],
    directory: str,
    timeout: float,
    thread_timings: Dict[str, float],
) -> None:
    output_path = (file_path.parent / entry[0]).absolute()
    config_for_stage_1_command = {
        "folder_path": file_path.parent.absolute(),
        "file_name": os.path.split(file_path)[1],
        "file_path": file_path.absolute(),
        "output": (output_path / "out"),
        "output_name": os.path.split(output_path)[1] + "/out",
    }
    shutil.rmtree(output_path, ignore_errors=True)
    os.mkdir(output_path)
    # fmt_command = f"rustfmt {file_path}"
    # subprocess.run(fmt_command.split(" "), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    command = entry[1].format(**config_for_stage_1_command)
    # command = f"rustc -C opt-level={flag} {file_path} -o {output_path / 'out'}"
    result = subprocess.run(command.split(" "), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    # command_2 = f"cp default.profraw code-{entry[0]}-{os.path.split(file_path)[1]}.profraw"
    # result2 = subprocess.run(
    #     command_2.split(" "),
    #     stdout=subprocess.DEVNULL,
    #     stderr=subprocess.PIPE
    # )
    with open(output_path / "compile.log", "w") as file:
        file.write(result.stderr.decode())
    if result.returncode == 0:
        try:
            with open(file_path.parent / (file_path.stem + ".txt")) as file:
                cli_args = file.read()
            config_for_stage_1_command["args"] = cli_args
            start_time = time.time()
            thread_timings[current_thread().name] = start_time
            run_result = subprocess.run(
                [f"{output_path / 'out'}", *cli_args.split(" ")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
            end_time = time.time() - thread_timings[current_thread().name]
            with open(Path(directory) / "time.log", "a") as file:
                file.write(f"{end_time}\n")
            with open(output_path / "output.log", "w") as file:
                file.write(run_result.stdout.decode())
                file.write(run_result.stderr.decode())
                file.write(f"Exit Code {run_result.returncode}")
        except subprocess.TimeoutExpired:
            with open(output_path / "output.log", "w") as file:
                file.write("Timeout")
    progress.update(1)


def main(threads: int = 4, timeout: float = 5.0, compile_only: bool = False, debug: bool = False) -> None:
    directory = "outRust"
    files = [dI for dI in os.listdir(directory) if os.path.isdir(os.path.join(directory, dI))]
    files.sort(key=lambda x: int(x.split("file")[1]))
    stage_1_entries = list(zip(config["stage_1_commands"].keys(), config["stage_1_commands"].values()))
    thread_timings = defaultdict(lambda x: 0.0)
    with typer.progressbar(label="Progress", length=len(files) * len(stage_1_entries)) as progress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            tasks = []
            for file in files:
                for entry in stage_1_entries:
                    tasks.append(
                        executor.submit(
                            compile_and_run,
                            Path(directory, file, file + ".rs"),
                            entry,
                            progress,
                            directory,
                            timeout,
                            thread_timings,
                        )
                    )
            for future in concurrent.futures.as_completed(tasks):
                future.result()
    for file in files:
        outputs = []
        for flag in stage_1_entries:
            path = Path(directory, file, f"{flag[0]}", "output.log")
            if path.exists():
                with open(path, "r") as output_file:
                    outputs.append(output_file.read())
            else:
                if debug:
                    outputs = []
                    print(f"{file}: Compilation Failure")
                    break
                else:
                    outputs.append("Compilation Failure")
        if len(outputs):
            if all(x == outputs[0] for x in outputs):
                print(f"{file}: All correct")
                # exit(0)
            else:
                print(f"{file}: Bug found")
                exit(1)


typer.run(main)
