import concurrent.futures
import os
import shutil
import subprocess
from pathlib import Path

import typer
from click._termui_impl import ProgressBar, V


def compile_and_run(file_path: Path, flag: str, progress: ProgressBar[V]) -> None:
    output_path = file_path.parent / f'O{flag}'
    shutil.rmtree(output_path, ignore_errors=True)
    os.mkdir(output_path)
    command = f"rustc -C opt-level={flag} {file_path} -o {output_path / 'out'}"
    result = subprocess.run(command.split(" "), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    with open(output_path / "compile.log", "w") as file:
        file.write(result.stderr.decode())
    if result.returncode == 0:
        run_result = subprocess.run(output_path / 'out', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with open(output_path / "output.log", "w") as file:
            file.write(run_result.stdout.decode())
            file.write(run_result.stderr.decode())
    progress.update(1)


def main(threads: int = 4, directory: str = "/Users/mayank/Documents/RustSmith/outRust") -> None:
    files = os.listdir(directory)
    files.sort()
    optimization_flags = ["0", "1", "2", "3", "s", "z"]
    with typer.progressbar(label="Progress", length=len(files) * len(optimization_flags)) as progress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            tasks = []
            for file in files:
                for flag in optimization_flags:
                    tasks.append(executor.submit(compile_and_run, Path(directory, file, file + ".rs"), flag, progress))
            for future in concurrent.futures.as_completed(tasks):
                future.result()
    for file in files:
        outputs = []
        for flag in optimization_flags:
            path = Path(directory, file, f"O{flag}", "output.log")
            if path.exists():
                with open(path, "r") as output_file:
                    outputs.append(output_file.read())
            else:
                print(f"{file}: Compilation Failure")
                break
        if len(outputs):
            print(f"{file}: {'All correct' if all(x == outputs[0] for x in outputs) else 'Bug found'}")


if __name__ == "__main__":
    typer.run(main)
