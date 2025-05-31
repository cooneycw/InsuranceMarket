# OSFI Intervention System Documentation

## Overview

The OSFI (Office of the Superintendent of Financial Institutions) intervention system is a regulatory mechanism in the insurance market simulation that activates when a player's company fails capital adequacy tests. This system implements realistic regulatory oversight by imposing penalty pricing decisions when companies become financially distressed.

## Trigger Condition

OSFI intervention activates when:
```python
pass_capital_test == 'Fail'
```

This flag is determined by the market simulation's financial analysis module and indicates that a company has failed to meet minimum capital requirements.

## Intervention Behavior by Game Difficulty

### Novice Games
- **Profit Margin Penalty**: 100 (10.0%)
- **Loss Trend Margin Penalty**: 0 (0.0%) - *No loss trend complexity*
- **Marketing Expense**: 0 (0.0%)

### Standard Games  
- **Profit Margin Penalty**: 80 (8.0%)
- **Loss Trend Margin Penalty**: 20 (2.0%)
- **Marketing Expense**: 0 (0.0%)

## Technical Implementation

### Location: `src_code/game/game_utils.py`

```python
if pass_capital_test == 'Fail':
    if is_novice:
        sel_profit_margin = 100  # 10.0% for novice penalty
        sel_loss_trend_margin = 0     # No loss trend complexity for novice
    else:
        sel_profit_margin = 80  # 8.0% for non-novice penalty
        sel_loss_trend_margin = 20    # 2.0% loss trend penalty for non-novice
    sel_mktg_expense = 0
    if player_type == 'user':
        decisions_locked = False  # Allow user to modify penalty values
    else:
        decisions_locked = True   # AI players auto-apply penalties
```

## User Experience Flow

### 1. Detection Phase
- Market simulation calculates capital ratios
- If below regulatory threshold, `pass_capital_test` is set to 'Fail'

### 2. Penalty Application
- System applies penalty default values based on game difficulty
- For user players: `decisions_locked = False` (waits for user input)
- For AI players: `decisions_locked = True` (auto-applies penalties)

### 3. User Decision Phase
- User receives penalty defaults in decision form
- User can modify values within normal game ranges
- User must submit decisions to proceed

### 4. Post-Simulation Messaging
- After year simulation completes, investigation message appears:
```
"OSFI reports company {player_name} is under investigation..."
```

## Database Fields Available to GUI

The GUI receives complete information through these database fields:

```python
# Current values (with penalties applied)
sel_profit_margin           # Penalty default value
sel_loss_trend_margin       # Penalty default value  
sel_exp_ratio_mktg         # Penalty default value

# Allowable ranges (currently unchanged during intervention)
sel_profit_margin_min      # Normal game minimum
sel_profit_margin_max      # Normal game maximum
sel_loss_trend_margin_min  # Normal game minimum
sel_loss_trend_margin_max  # Normal game maximum
sel_exp_ratio_mktg_min     # Normal game minimum
sel_exp_ratio_mktg_max     # Normal game maximum

# Status flags
decisions_locked           # False for users during intervention
decisions_game_stage       # "decisions" or "pre-game"
```

## Current Limitations & Considerations

### 1. Range Restrictions
**Current Behavior**: Penalty defaults are applied, but users can still adjust within normal game ranges.

**Potential Issue**: Users can potentially reduce penalties below regulatory intent.

**Example**: 
- Novice OSFI penalty: 10.0% profit margin
- User can still adjust down to 0.0% profit margin (normal minimum)

### 2. No Range Modification
The min/max allowable ranges are **not modified** during OSFI intervention. They remain at normal game limits:

**Novice Games:**
- Profit Margin: 0-100 (0.0%-10.0%)
- Loss Trend: 0-0 (0.0%-0.0%)
- Marketing: 0-50 (0.0%-5.0%)

**Standard Games:**
- Profit Margin: 0-80 (0.0%-8.0%) 
- Loss Trend: -30 to +30 (-3.0% to +3.0%)
- Marketing: 0-50 (0.0%-5.0%)

### 3. Messaging Asymmetry
- **OSFI Fail**: Clear intervention messaging
- **OSFI Pass**: No regulatory approval messaging (recently fixed)

## Decimal Storage System

All values use 10x factor storage:
- **Display**: Divide by 10 (e.g., 100 → 10.0%)
- **Calculations**: Divide by 1000 (e.g., 100 → 0.10 = 10%)
- **Storage**: Integer values (e.g., 10.0% → 100)

## Recommendations for Enhancement

### 1. Implement Range Restrictions During Intervention
```python
if pass_capital_test == 'Fail':
    # Apply penalties AND restrict ranges
    if is_novice:
        sel_profit_margin = 100
        sel_profit_margin_min = 90   # Force near-penalty minimum
        sel_profit_margin_max = 100  # Cap at penalty level
    else:
        sel_profit_margin = 80
        sel_profit_margin_min = 70   # Force near-penalty minimum  
        sel_profit_margin_max = 80   # Cap at penalty level
```

### 2. Add Regulatory Status Indicators
- Add `regulatory_status` field: "Normal", "Under Investigation", "Intervention"
- Provide clear GUI indicators of regulatory oversight level

### 3. Implement Graduated Penalties
- Light intervention: Restricted ranges only
- Heavy intervention: Fixed penalty values
- Based on severity of capital shortfall

## File Locations

- **Core Logic**: `src_code/game/game_utils.py` (process_indications function)
- **Database Models**: `src_code/models/models.py` (Decisions table)
- **Database Utils**: `src_code/models/db_utils.py` (update_decisions function)
- **Game Flow**: `src_code/game/start_game.py` (game_flow method)
- **Configuration**: `config/config.py` (init_decisions ranges)

## Testing Scenarios

### To Test OSFI Intervention:
1. Force capital test failure in market simulation
2. Verify penalty values are applied correctly by difficulty level
3. Confirm user can modify within allowable ranges
4. Check investigation messaging appears post-simulation
5. Validate GUI receives all necessary range information

### Test Cases:
- Novice game with capital failure
- Standard game with capital failure  
- AI player vs user player intervention
- Range boundary testing
- Multiple consecutive intervention years 