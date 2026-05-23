# Trading Decision Prompt

## Input Data
You will receive:
- Stock symbol and name
- Current price and historical data
- Technical indicators (MA, RSI, MACD, etc.)
- Market sentiment indicators
- Current position information

## Decision Framework
1. **Technical Analysis**: Evaluate indicator signals
2. **Risk Assessment**: Check position limits and volatility
3. **Signal Confirmation**: Look for multiple confirming signals
4. **Final Decision**: Generate BUY/SELL/HOLD/WATCH with confidence

## Action Guidelines
- **BUY**: Strong upward signals, confidence > 70
- **SELL**: Reversal signals or profit-taking, confidence > 65
- **HOLD**: No clear signals, maintain current position
- **WATCH**: Potential setup forming, wait for confirmation

## Position Sizing
- Max single position: 30% of portfolio
- Scale in/out based on confidence:
  - 90-100: Full allocation
  - 70-89: Half allocation
  - 50-69: Quarter allocation
