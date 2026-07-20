"""用 Zig 交叉编译可复现的 Linux ELF 共享库测试夹具。"""

from pathlib import Path
import hashlib
import os
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "fixtures" / "src"
OUTPUT = ROOT / "tests" / "fixtures" / "generated"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    zig = shutil.which("zig")
    if zig is None:
        raise SystemExit("需要已安装的 zig 来构建 Linux ELF 测试夹具")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["ZIG_GLOBAL_CACHE_DIR"] = str(OUTPUT / ".zig-global-cache")
    environment["ZIG_LOCAL_CACHE_DIR"] = str(OUTPUT / ".zig-local-cache")
    builds = (
        ("symbolic.c", "libsymbolic.so", "-O0", "-g"),
        ("stripped.c", "libstripped.so", "-O2", "-s"),
        ("control_flow.c", "libcontrol_flow.so", "-O2", "-fno-unroll-loops"),
    )
    for source_name, output_name, *flags in builds:
        output = OUTPUT / output_name
        subprocess.run(
            [
                zig,
                "cc",
                "-target",
                "x86_64-linux-gnu",
                "-shared",
                "-fPIC",
                "-nostdlib",
                *flags,
                str(SOURCE / source_name),
                "-o",
                str(output),
            ],
            check=True,
            env=environment,
        )
        print(f"{output.name} {sha256(output)}")


if __name__ == "__main__":
    main()
