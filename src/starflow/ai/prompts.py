from pathlib import Path

from starflow.i18n.guard import assert_authored


class PromptLibrary:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def read(self, name: str) -> str:
        if name != Path(name).name or not name.endswith(".txt"):
            raise ValueError("prompt name must be a txt file name")
        text = (self._directory / name).read_text(encoding="utf-8").strip()
        assert_authored(text)
        return text

    def assistant_system(self) -> str:
        text = self.read("assistant_system.txt")
        if "json" not in text:
            raise ValueError("assistant prompt must mention json")
        return text
