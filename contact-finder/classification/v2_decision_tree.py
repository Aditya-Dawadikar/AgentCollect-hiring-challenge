"""Decision-tree confidence classifier (v2), trained at construction time
on synthetic data from `training_data.generate_training_set()`.
See ADR-0005 for the training-data design and confidence derivation."""

from sklearn.tree import DecisionTreeClassifier

from classification.base_classifier import BaseClassifier
from classification.features import signals_to_vector
from classification.training_data import generate_training_set
from config import settings

BUCKET_MIDPOINT = {"high": 90, "medium": 70, "low": 45, "cannot_verify": 10}


class DecisionTreeConfidenceClassifier(BaseClassifier):
    def __init__(self, threshold: int = settings.CONFIDENCE_THRESHOLD,
                 max_depth: int = 4, seed: int = 42):
        self.threshold = threshold
        X, y = generate_training_set(seed=seed)
        self.model = DecisionTreeClassifier(max_depth=max_depth, random_state=seed)
        self.model.fit(X, y)

    def score(self, signals: dict) -> dict:
        if signals["sources_count"] == 0:
            return {
                "confidence_score": 0,
                "classification": "cannot_verify",
                "needs_human_review": True,
            }

        vector = signals_to_vector(signals)
        proba = self.model.predict_proba([vector])[0]
        confidence_score = int(round(
            sum(p * BUCKET_MIDPOINT[c] for c, p in zip(self.model.classes_, proba))
        ))
        classification = str(self.model.classes_[proba.argmax()])

        return {
            "confidence_score": confidence_score,
            "classification": classification,
            "needs_human_review": confidence_score < self.threshold,
        }
