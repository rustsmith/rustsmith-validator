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

config = {
    "stage_1_commands": {
        "O0": "./build/aarch64-apple-darwin/stage2/bin/rustc -Zmir-opt-level=0 {file_path} -o {output}",
        "O1": "./build/aarch64-apple-darwin/stage2/bin/rustc -Zmir-opt-level=1 {file_path} -o {output}",
        "O2": "./build/aarch64-apple-darwin/stage2/bin/rustc -Zmir-opt-level=2 {file_path} -o {output}",
        "O3": "./build/aarch64-apple-darwin/stage2/bin/rustc -Zmir-opt-level=3 {file_path} -o {output}",
        "OE": "./build/aarch64-apple-darwin/stage2/bin/rustc -Zexperimental-mir-optimizations {file_path} -o {output}",
        # "O0": "rustc -Zmir-opt-level=0 {file_path} -o {output}",
        # "O1": "rustc -Zmir-opt-level=1 {file_path} -o {output}",
        # "O2": "rustc -Zmir-opt-level=2 {file_path} -o {output}",
        # "O3": "rustc -Zmir-opt-level=3 {file_path} -o {output}",
        # "O0": "rustc -C opt-level=0 {file_path} -o {output}",
        # "O1": "rustc -C opt-level=1 {file_path} -o {output}",
        # "O2": "rustc -C opt-level=2 {file_path} -o {output}",
        # "O3": "rustc -C opt-level=3 {file_path} -o {output}",
        # "Os": "rustc -C opt-level=s {file_path} -o {output}",
        # "Oz": "rustc -C opt-level=z {file_path} -o {output}",
        # "C0": "/Users/mayank/Downloads/build/rustc-clif -C opt-level=0 {file_path} -o {output}",
        # "C1": "/Users/mayank/Downloads/build/rustc-clif -C opt-level=1 {file_path} -o {output}",
        # "C2": "/Users/mayank/Downloads/build/rustc-clif -C opt-level=2 {file_path} -o {output}",
        # "C3": "/Users/mayank/Downloads/build/rustc-clif -C opt-level=3 {file_path} -o {output}",
        # "Cs": "/Users/mayank/Downloads/build/rustc-clif -C opt-level=s {file_path} -o {output}",
        # "Cz": "/Users/mayank/Downloads/build/rustc-clif -C opt-level=z {file_path} -o {output}",
        # "GO1": 'docker run --rm -v {folder_path}:/usr/src/myapp -w /usr/src/myapp philberty/gccrs:latest gccrs -g -O1 {file_name} -o {output}',
    }
}


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
    }
    shutil.rmtree(output_path, ignore_errors=True)
    os.mkdir(output_path)
    fmt_command = f"rustfmt {file_path}"
    subprocess.run(fmt_command.split(" "), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    command = entry[1].format(**config_for_stage_1_command)
    # command = f"rustc -C opt-level={flag} {file_path} -o {output_path / 'out'}"
    result = subprocess.run(
        command.split(" "), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd="/Users/mayank/Documents/rust"
    )
    command_2 = f"cp default.profraw code-{entry[0]}-{os.path.split(file_path)[1]}.profraw"
    result2 = subprocess.run(
        command_2.split(" "), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd="/Users/mayank/Documents/rust"
    )
    with open(output_path / "compile.log", "w") as file:
        file.write(result.stderr.decode())
    if result.returncode == 0:
        try:
            with open(file_path.parent / (file_path.stem + ".txt")) as file:
                cli_args = file.read()
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


def main(threads: int = 4, timeout: float = 5.0, compile_only: bool = False) -> None:
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
            path = Path(directory, file, f"O{flag}", "output.log")
            if path.exists():
                with open(path, "r") as output_file:
                    outputs.append(output_file.read())
            else:
                print(f"{file}: Compilation Failure")
                break
        if len(outputs):
            print(f"{file}: {'All correct' if all(x == outputs[0] for x in outputs) else 'Bug found'}")


typer.run(main)
