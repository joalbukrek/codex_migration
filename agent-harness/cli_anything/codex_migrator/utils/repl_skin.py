from __future__ import annotations


class ReplSkin:
    def __init__(self, name: str, version: str = "0.1.0") -> None:
        self.name = name
        self.version = version

    def print_banner(self) -> None:
        print(f"{self.name} {self.version}")
        print("Type 'help' for commands or 'quit' to exit.")

    def print_goodbye(self) -> None:
        print("bye")

    def success(self, message: str) -> None:
        print(f"OK: {message}")

    def error(self, message: str) -> None:
        print(f"ERROR: {message}")

    def warning(self, message: str) -> None:
        print(f"WARN: {message}")

    def info(self, message: str) -> None:
        print(message)

    def table(self, headers, rows) -> None:
        widths = [len(str(header)) for header in headers]
        for row in rows:
            for index, cell in enumerate(row):
                widths[index] = max(widths[index], len(str(cell)))
        print("  ".join(str(header).ljust(widths[index]) for index, header in enumerate(headers)))
        print("  ".join("-" * width for width in widths))
        for row in rows:
            print("  ".join(str(cell).ljust(widths[index]) for index, cell in enumerate(row)))
