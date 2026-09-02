class ContextAnalyzer:
    def analyze(
        self,
        transaction_type: str = None,
        transaction_amount: float = 0.0,
        known_contact: bool = False,
        urgency: bool = False,
        historical_fraud_flag: bool = False
    ) -> float:
        """
        Lightweight deterministic contextual risk analyzer.
        Returns a score in [0.0, 1.0].
        """
        score = 0.0
        
        # Base modifiers
        if not known_contact:
            score += 0.3
            
        if historical_fraud_flag:
            score += 0.5
            
        # Transaction context
        if transaction_type in ["fund_transfer", "password_reset", "account_recovery"]:
            score += 0.2
            if transaction_amount > 10000:
                score += 0.2
            elif transaction_amount > 1000:
                score += 0.1
                
        # Urgency
        if urgency:
            score += 0.15
            
        return min(max(score, 0.0), 1.0)
