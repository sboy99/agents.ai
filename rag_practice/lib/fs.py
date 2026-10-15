import os


class FileSystem:
    def __init__(self, base_path: str = "data"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def read(self, filename: str) -> str:
        with open(os.path.join(self.base_path, filename), "r", encoding="utf-8") as f:
            return f.read()

    def write(self, filename: str, content: str) -> None:
        with open(os.path.join(self.base_path, filename), "w", encoding="utf-8") as f:
            f.write(content)

    def list_files(self) -> list[str]:
        return [
            f
            for f in os.listdir(self.base_path)
            if os.path.isfile(os.path.join(self.base_path, f))
        ]

    def exists(self, filename: str) -> bool:
        return os.path.exists(os.path.join(self.base_path, filename))
