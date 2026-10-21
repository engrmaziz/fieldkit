"""Unit tests for cross-camera person Re-Identification and spatial topology matching."""

from __future__ import annotations

import numpy as np
import pytest
from fieldkit_vision.reid import (
    CameraTopology,
    GlobalPersonRegistry,
    OSNetFeatureExtractor,
    PersonCrop,
    PersonTrackEmbedding,
    compute_cosine_similarity,
    extract_person_crop,
)


def test_topology_loader() -> None:
    """Verify loading camera topology from YAML."""
    topology = CameraTopology.from_yaml("configs/topology.yaml")
    assert topology.plant_id == "DE-HAM"
    assert len(topology.cameras) == 4

    # Check transit window between cam1_press and cam2_logistics
    transition = topology.get_transition("cam1_press", "cam2_logistics")
    assert transition is not None
    assert transition.min_transit_time_sec == 3.0
    assert transition.max_transit_time_sec == 60.0

    # Unreachable camera pair should return None if not defined
    assert topology.is_transit_valid("cam1_press", "cam2_logistics", elapsed_sec=5.0) is True
    assert topology.is_transit_valid("cam1_press", "cam2_logistics", elapsed_sec=1.0) is False  # Too fast
    assert topology.is_transit_valid("cam1_press", "cam2_logistics", elapsed_sec=100.0) is False  # Too slow


def test_person_crop_extraction_and_sharpness() -> None:
    """Verify extracting crop from image, bounding box clipping, and sharpness calculation."""
    # Synthetic frame (1080 x 1920)
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    # Add a high-contrast pattern in person region
    img[200:600, 400:600] = 180
    img[250:350, 450:550] = 40

    box = [400, 200, 600, 600]  # x1, y1, x2, y2 (200x400 = 80,000 area)
    crop = extract_person_crop(img, box, track_id=1, timestamp=10.0)

    assert crop is not None
    assert isinstance(crop, PersonCrop)
    assert crop.crop_image.shape[0] == 400
    assert crop.crop_image.shape[1] == 200
    assert crop.area == 80000
    assert crop.sharpness > 0.0

    # Too small crop should return None
    small_box = [10, 10, 30, 30]  # 20x20 = 400 area < 2500
    small_crop = extract_person_crop(img, small_box, track_id=2, timestamp=10.0, min_area=2500)
    assert small_crop is None


def test_osnet_embedding_normalization() -> None:
    """Verify feature extractor produces a 512-dim unit-normalized embedding."""
    extractor = OSNetFeatureExtractor()
    synthetic_crop = np.random.randint(0, 255, (256, 128, 3), dtype=np.uint8)

    emb = extractor.extract(synthetic_crop)
    assert emb.shape == (512,)
    # Norm should be approximately 1.0
    norm = np.linalg.norm(emb)
    assert pytest.approx(norm, rel=1e-3) == 1.0


def test_cosine_similarity() -> None:
    """Verify cosine similarity between unit vectors."""
    v1 = np.ones(512, dtype=np.float32)
    v1 /= np.linalg.norm(v1)

    # Identical vector
    sim_self = compute_cosine_similarity(v1, v1)
    assert pytest.approx(sim_self, abs=1e-4) == 1.0

    # Orthogonal vector
    v2 = np.copy(v1)
    v2[:256] = -v2[:256]
    v2 /= np.linalg.norm(v2)
    sim_ortho = compute_cosine_similarity(v1, v2)
    assert abs(sim_ortho) < 0.1


def test_cross_camera_reid_match_with_topology() -> None:
    """Verify cross-camera Re-ID matching respects similarity and spatial-temporal constraints."""
    topology = CameraTopology.from_yaml("configs/topology.yaml")
    registry = GlobalPersonRegistry(topology=topology, similarity_threshold=0.75)

    # Person A on cam1_press at t=10.0
    feature_a = np.random.randn(512).astype(np.float32)
    feature_a /= np.linalg.norm(feature_a)

    track_a = PersonTrackEmbedding(
        camera_id="cam1_press",
        track_id=101,
        first_seen=8.0,
        last_seen=10.0,
        embedding=feature_a,
    )
    person_id_a = registry.register_or_match(track_a)
    assert person_id_a.startswith("person_")

    # Person A arrives at cam2_logistics at t=15.0 (elapsed = 5.0s, valid in [3.0, 60.0])
    # Embedding with high similarity (noise added)
    feature_b = feature_a + np.random.randn(512).astype(np.float32) * 0.01
    feature_b /= np.linalg.norm(feature_b)

    track_b = PersonTrackEmbedding(
        camera_id="cam2_logistics",
        track_id=202,
        first_seen=15.0,
        last_seen=18.0,
        embedding=feature_b,
    )
    person_id_b = registry.register_or_match(track_b)

    # Should match Person A and assign the same global person ID
    assert person_id_b == person_id_a

    # Person C at cam2_logistics at t=11.0 (elapsed = 1.0s, physically impossible)
    track_c = PersonTrackEmbedding(
        camera_id="cam2_logistics",
        track_id=203,
        first_seen=11.0,
        last_seen=12.0,
        embedding=feature_a,  # Same features but physically impossible timing
    )
    person_id_c = registry.register_or_match(track_c)
    # Must NOT match person_id_a because timing violates topology
    assert person_id_c != person_id_a


def test_global_person_registry_journey() -> None:
    """Verify person journey reconstruction across camera transitions."""
    topology = CameraTopology.from_yaml("configs/topology.yaml")
    registry = GlobalPersonRegistry(topology=topology, similarity_threshold=0.75)

    base_feature = np.random.randn(512).astype(np.float32)
    base_feature /= np.linalg.norm(base_feature)

    # 1. Cam1 Press at t=10
    t1 = PersonTrackEmbedding("cam1_press", 1, 5.0, 10.0, base_feature)
    pid = registry.register_or_match(t1)

    # 2. Cam2 Logistics at t=16
    t2 = PersonTrackEmbedding("cam2_logistics", 5, 16.0, 22.0, base_feature)
    pid2 = registry.register_or_match(t2)
    assert pid2 == pid

    # 3. Cam3 Assembly at t=28
    t3 = PersonTrackEmbedding("cam3_assembly", 9, 28.0, 35.0, base_feature)
    pid3 = registry.register_or_match(t3)
    assert pid3 == pid

    journey = registry.get_journey(pid)
    assert len(journey) == 3
    assert journey[0].camera_id == "cam1_press"
    assert journey[1].camera_id == "cam2_logistics"
    assert journey[2].camera_id == "cam3_assembly"
