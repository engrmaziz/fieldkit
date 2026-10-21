"""Local lightweight model registry supporting candidate, production, and rollback lifecycle."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class ModelStage(StrEnum):
    CANDIDATE = "candidate"
    PRODUCTION = "production"
    ARCHIVED = "archived"


@dataclass
class ModelArtifact:
    model_name: str
    version: str
    stage: ModelStage
    artifact_path: str
    metrics: dict[str, float] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    promoted_by: str | None = None
    promotion_notes: str | None = None


class ModelRegistry:
    """Local file-based model registry for air-gapped industrial deployment."""

    def __init__(self, registry_root: Path | str = "data/models/registry") -> None:
        self.root = Path(registry_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_file = self.root / "registry_manifest.json"
        self._models: dict[str, list[ModelArtifact]] = self._load()

    def _load(self) -> dict[str, list[ModelArtifact]]:
        if not self.manifest_file.exists():
            return {}
        try:
            raw = json.loads(self.manifest_file.read_text(encoding="utf-8"))
            out: dict[str, list[ModelArtifact]] = {}
            for m_name, entries in raw.items():
                out[m_name] = [
                    ModelArtifact(
                        model_name=e["model_name"],
                        version=e["version"],
                        stage=ModelStage(e["stage"]),
                        artifact_path=e["artifact_path"],
                        metrics=e.get("metrics", {}),
                        parameters=e.get("parameters", {}),
                        created_at=e.get("created_at", ""),
                        promoted_by=e.get("promoted_by"),
                        promotion_notes=e.get("promotion_notes"),
                    )
                    for e in entries
                ]
            return out
        except Exception:
            return {}

    def _save(self) -> None:
        raw: dict[str, list[dict[str, Any]]] = {}
        for m_name, entries in self._models.items():
            raw[m_name] = []
            for e in entries:
                d = asdict(e)
                d["stage"] = e.stage.value
                raw[m_name].append(d)

        self.manifest_file.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def register_model(
        self,
        model_name: str,
        version: str,
        artifact_path: str,
        stage: ModelStage = ModelStage.CANDIDATE,
        metrics: dict[str, float] | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> ModelArtifact:
        """Register a new candidate or production model."""
        artifact = ModelArtifact(
            model_name=model_name,
            version=version,
            stage=stage,
            artifact_path=artifact_path,
            metrics=metrics or {},
            parameters=parameters or {},
        )

        if model_name not in self._models:
            self._models[model_name] = []

        # If registering as production, archive previous production versions
        if stage == ModelStage.PRODUCTION:
            for existing in self._models[model_name]:
                if existing.stage == ModelStage.PRODUCTION:
                    existing.stage = ModelStage.ARCHIVED

        self._models[model_name].append(artifact)
        self._save()
        return artifact

    def get_production_model(self, model_name: str) -> ModelArtifact | None:
        """Retrieve the active production model version for a product/task."""
        entries = self._models.get(model_name, [])
        for e in reversed(entries):
            if e.stage == ModelStage.PRODUCTION:
                return e
        return None

    def promote_candidate(
        self,
        model_name: str,
        version: str,
        promoted_by: str = "mehmet",
        notes: str = "Passed shadow evaluation criteria",
    ) -> bool:
        """Promote a candidate model version to production and archive current production model."""
        entries = self._models.get(model_name, [])
        target = None
        for e in entries:
            if e.version == version:
                target = e
                break

        if not target:
            return False

        for e in entries:
            if e.stage == ModelStage.PRODUCTION:
                e.stage = ModelStage.ARCHIVED

        target.stage = ModelStage.PRODUCTION
        target.promoted_by = promoted_by
        target.promotion_notes = notes
        self._save()
        return True

    def rollback_to_version(self, model_name: str, target_version: str) -> bool:
        """Rollback production to a specific prior version."""
        entries = self._models.get(model_name, [])
        target = None
        for e in entries:
            if e.version == target_version:
                target = e
                break

        if not target:
            return False

        for e in entries:
            if e.stage == ModelStage.PRODUCTION:
                e.stage = ModelStage.ARCHIVED

        target.stage = ModelStage.PRODUCTION
        target.promotion_notes = f"Rollback to {target_version}"
        self._save()
        return True

    def list_models(self, model_name: str | None = None) -> list[ModelArtifact]:
        if model_name:
            return self._models.get(model_name, [])
        all_models = []
        for entries in self._models.values():
            all_models.extend(entries)
        return all_models
