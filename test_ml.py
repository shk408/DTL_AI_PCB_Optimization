from pathlib import Path

from pcb_sustainability.ingestion import load_bom
from pcb_sustainability.ml import apply_ml_predictions, predict_bom, train_predictor_from_csv
from pcb_sustainability.scoring import score_bom


ROOT = Path(__file__).resolve().parents[1]


def test_ml_predictor_trains_and_predicts_scores():
    predictor = train_predictor_from_csv(ROOT / "samples" / "ml_training_components.csv")
    bom = load_bom(ROOT / "samples" / "sample_bom.csv")
    predictions = predict_bom(bom, predictor)
    assert "ESP32-WROOM-32" in predictions
    assert 0 <= predictions["ESP32-WROOM-32"].predicted_score <= 100
    assert predictions["ESP32-WROOM-32"].confidence > 0


def test_ml_predictions_blend_into_component_scores():
    predictor = train_predictor_from_csv(ROOT / "samples" / "ml_training_components.csv")
    bom = load_bom(ROOT / "samples" / "sample_bom.csv")
    scores, _ = score_bom(bom)
    blended, summary = apply_ml_predictions(scores, predict_bom(bom, predictor), blend_weight=0.25)
    assert summary["ml_enabled"] is True
    assert "ml_prediction" in blended[0].enrichment
    assert 0 <= summary["summary_score"] <= 100
