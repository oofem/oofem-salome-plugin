# OOFEMState.py
import json
import traceback

ATTR_NAME = "OOFEM_OOFEMState_v1"   # unique key stored on the Study

class OOFEMState:
    @staticmethod
    def load(study):
        """
        Load plugin state from the Study. Returns a dict (empty if none).
        Uses Study.GetString(key) as the persistent storage.
        """
        try:
            if study is None:
                return {}
            # Preferred: use GetString if available
            if hasattr(study, "GetString"):
                try:
                    raw = study.GetString(ATTR_NAME)
                except Exception:
                    raw = None
                if raw:
                    try:
                        return json.loads(raw)
                    except Exception:
                        # corrupted JSON: return empty and print traceback
                        traceback.print_exc()
                        return {}
            # Fallback: try GetVariableNames / GetString with different semantics
            if hasattr(study, "IsString") and hasattr(study, "GetString"):
                try:
                    if study.IsString(ATTR_NAME):
                        raw = study.GetString(ATTR_NAME)
                        return json.loads(raw) if raw else {}
                except Exception:
                    pass
        except Exception:
            traceback.print_exc()
        return {}

    @staticmethod
    def save(study, state_dict):
        """
        Save plugin state (dict) into the Study using SetString(key, json).
        Returns True on success, False otherwise.
        """
        try:
            if study is None:
                return False
            payload = json.dumps(state_dict)
            if hasattr(study, "SetString"):
                try:
                    study.SetString(ATTR_NAME, payload)
                    return True
                except Exception:
                    traceback.print_exc()
                    return False
            # No SetString available: fail gracefully
        except Exception:
            traceback.print_exc()
        return False
