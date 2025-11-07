from pathlib import Path
from typing import Optional

import yaml

from pkb.core.exceptions import ConfigurationException


DEFAULT_CONFIG = {
    "sources": {
        "zotero": {
            "enabled": False,
            "csv_path": "~/Zotero/export.csv",
        },
        "obsidian": {
            "enabled": False,
            "vault_path": "~/Documents/ObsidianVault",
        },
    },
    "backends": {
        "elasticsearch": {
            "enabled": False,
            "host": "localhost",
            "port": 9200,
            "indexes": {
                "keyword": "pkb_keyword",
                "vector": "pkb_vector",
                "semantic": "pkb_semantic",
            },
        },
        "qdrant": {
            "enabled": False,
            "host": "localhost",
            "port": 6333,
            "collection": "pkb_collection",
        },
    },
    "indexing": {
        "chunk_size": 512,
        "chunk_overlap": 50,
        "min_chunk_size": 100,
        "state_db_path": "~/.pkb/state.db",
    },
    "embeddings": {
        "model": "sentence-transformers/all-MiniLM-L6-v2",
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8000,
    },
}


class Config:
    """
    Configuration manager for PKB.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config file (default: ~/.pkb/config.yaml)
        """
        if config_path:
            self.config_path = Path(config_path).expanduser()
        else:
            self.config_path = Path.home() / ".pkb" / "config.yaml"

        self.config = self._load_config()

    def _load_config(self) -> dict:
        """
        Load configuration from file or create default.
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    config = yaml.safe_load(f)
                    # Merge with defaults for missing keys
                    return self._merge_with_defaults(config)
            except Exception as e:
                raise ConfigurationException(f"Failed to load config: {e}")
        else:
            # Create default config
            return DEFAULT_CONFIG.copy()

    def _merge_with_defaults(self, config: dict) -> dict:
        """
        Merge user config with defaults.
        """
        merged = DEFAULT_CONFIG.copy()

        for key, value in config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key].update(value)
            else:
                merged[key] = value

        return merged

    def save(self) -> None:
        """
        Save configuration to file.
        """
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.config_path, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            raise ConfigurationException(f"Failed to save config: {e}")

    def get(self, key: str, default=None):
        """
        Get configuration value by dot-separated key.

        Args:
            key: Dot-separated key (e.g., 'sources.zotero.csv_path')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value) -> None:
        """
        Set configuration value by dot-separated key.

        Args:
            key: Dot-separated key (e.g., 'sources.zotero.enabled')
            value: Value to set
        """
        keys = key.split(".")
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def get_enabled_sources(self) -> list[str]:
        """
        Get list of enabled source names.
        """
        sources = []
        for name, config in self.config.get("sources", {}).items():
            if config.get("enabled", False):
                sources.append(name)
        return sources

    def get_enabled_backends(self) -> list[str]:
        """
        Get list of enabled backend names.
        """
        backends = []
        for name, config in self.config.get("backends", {}).items():
            if config.get("enabled", False):
                backends.append(name)
        return backends

    def __repr__(self) -> str:
        return f"Config(config_path={self.config_path})"