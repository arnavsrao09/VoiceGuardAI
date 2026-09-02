from typing import List

class WorkflowEngine:
    def evaluate(self, risk_score: float, transaction_type: str = None) -> List[str]:
        """
        Simple rule-based workflow engine.
        Returns a list of recommended actions.
        """
        actions = []
        
        if risk_score >= 0.80:
            actions.append("hold_transaction")
            actions.append("require_mfa")
            actions.append("notify_supervisor")
            
        elif risk_score >= 0.60:
            actions.append("require_mfa")
            if transaction_type in ["fund_transfer", "password_reset"]:
                actions.append("hold_transaction")
                
        elif risk_score >= 0.30:
            actions.append("log_for_review")
            
        return actions

workflow_engine = WorkflowEngine()
