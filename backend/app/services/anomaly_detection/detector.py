"""Explainable AI Anomaly Detection Service using Isolation Forest and Statistical Heuristics.

Advisory Only: Never automatically rejects records or marks fraud without verifier confirmation.
Gracefully falls back to rule-based analysis if scikit-learn is unavailable or dataset is small.
"""
from typing import List, Dict, Any, Optional
import numpy as np

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class AnomalyDetectionService:
    @staticmethod
    def detect_enrollment_anomalies(
        institution_metrics: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Analyzes institution-level statistics:
        - Total students
        - Duplicate percentage
        - Quota overshoot percentage
        - Category skewness
        
        Returns explainable anomaly alerts with contributing feature reasons.
        """
        if not institution_metrics or len(institution_metrics) < 3:
            # Fallback to deterministic heuristic when institution count is too small for ML
            return AnomalyDetectionService._rule_based_anomalies(institution_metrics)

        # Features: [total_students, duplicate_rate, quota_overshoot_rate, nri_rate]
        feature_matrix = []
        valid_entries = []
        for item in institution_metrics:
            total = max(item.get("total_students", 0), 1)
            duplicates = item.get("duplicate_count", 0)
            overshoot = item.get("quota_overshoot", 0)
            nri_count = item.get("nri_count", 0)

            dup_rate = duplicates / total
            overshoot_rate = overshoot / total
            nri_rate = nri_count / total

            feature_matrix.append([total, dup_rate, overshoot_rate, nri_rate])
            valid_entries.append(item)

        X = np.array(feature_matrix)

        anomalies = []
        if SKLEARN_AVAILABLE and len(valid_entries) >= 5:
            # Fit IsolationForest with 0.15 contamination expectation
            try:
                clf = IsolationForest(contamination=0.15, random_state=42)
                preds = clf.fit_predict(X)
                scores = clf.decision_function(X)

                for idx, pred in enumerate(preds):
                    if pred == -1: # Anomaly flagged by Isolation Forest
                        entry = valid_entries[idx]
                        reasons = []
                        if X[idx][1] > 0.05:
                            reasons.append(f"High duplicate rate: {X[idx][1]*100:.1f}%")
                        if X[idx][2] > 0.10:
                            reasons.append(f"Significant intake capacity overshoot: {X[idx][2]*100:.1f}%")
                        if X[idx][3] > 0.20:
                            reasons.append(f"Unusually high NRI/quota ratio: {X[idx][3]*100:.1f}%")
                        if not reasons:
                            reasons.append(f"Multivariate statistical outlier score ({scores[idx]:.3f})")

                        anomalies.append({
                            "institution_id": entry.get("institution_id"),
                            "institution_name": entry.get("institution_name"),
                            "detection_method": "IsolationForest_ML",
                            "anomaly_score": float(scores[idx]),
                            "is_advisory": True,
                            "reasons": reasons,
                            "recommendation": "Review recent batch uploads and student registrations for verification."
                        })
                return anomalies
            except Exception:
                pass

        # Rule-based fallback
        return AnomalyDetectionService._rule_based_anomalies(institution_metrics)

    @staticmethod
    def _rule_based_anomalies(institution_metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        anomalies = []
        for item in institution_metrics:
            total = max(item.get("total_students", 0), 1)
            duplicates = item.get("duplicate_count", 0)
            overshoot = item.get("quota_overshoot", 0)

            reasons = []
            if (duplicates / total) > 0.05:
                reasons.append(f"Duplicate registration rate exceeds 5% ({duplicates}/{total})")
            if overshoot > 0:
                reasons.append(f"Intake exceeded by {overshoot} students")

            if reasons:
                anomalies.append({
                    "institution_id": item.get("institution_id"),
                    "institution_name": item.get("institution_name"),
                    "detection_method": "Deterministic_Heuristic",
                    "anomaly_score": None,
                    "is_advisory": True,
                    "reasons": reasons,
                    "recommendation": "Manual verifier review advised for institution quotas and upload batches."
                })
        return anomalies

anomaly_service = AnomalyDetectionService()
