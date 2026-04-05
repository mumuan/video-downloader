import json
import os

class Config:
    def __init__(self, app_data_dir: str):
        self.app_data_dir = app_data_dir
        self.config_file = os.path.join(app_data_dir, "config.json")
        self._output_dir = ""
        self._load()

    def _load(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._output_dir = data.get('output_dir', self._default_output_dir())
        else:
            self._output_dir = self._default_output_dir()

    def _default_output_dir(self) -> str:
        videos = os.path.join(os.path.expanduser("~"), "Videos", "bilibili")
        os.makedirs(videos, exist_ok=True)
        return videos

    @property
    def output_dir(self) -> str:
        return self._output_dir

    @output_dir.setter
    def output_dir(self, value: str):
        os.makedirs(value, exist_ok=True)
        self._output_dir = value
        self.save()

    def save(self):
        os.makedirs(self.app_data_dir, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump({'output_dir': self._output_dir}, f, ensure_ascii=False, indent=2)