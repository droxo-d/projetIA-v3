import joblib
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"


def load_pipeline():
    """Loads the single fitted sklearn Pipeline (log1p -> scale -> KMeans)."""
    pipeline_path = MODEL_DIR / "rfm_pipeline.pkl"
    if not pipeline_path.exists():
        raise FileNotFoundError(
            "model/rfm_pipeline.pkl not found. Run export_pipeline_snippet.py "
            "at the end of your notebook to generate it, then copy it here."
        )
    return joblib.load(pipeline_path)
