"""FANTASMA / OBSERVATORIO - Signals Package (Expanded)"""
from .banxico import get_c1_fix, get_c2_tiie, get_c4_reservas
from .cftc import get_c3_cftc
from .fred import get_g1_vix, get_g3_us10y, get_c5_spread, get_fed_funds_rate
from .yahoo import get_g2_dxy, get_g4_hy_spread, get_g5_copper, get_usdmxn
from .google_trends import get_g6_google_trends
from .volatility import get_g7_volatility
from .ormuz import get_o1_brent, get_o2_gas_europe, get_o3_usdchf, get_o4_sofr, get_o5_war_risk
from .mexico import get_m1_usdmxn, get_m2_corn, get_m3_urea
from .carry_trade import get_g8_carry_trade

__all__ = [
    'get_c1_fix', 'get_c2_tiie', 'get_c3_cftc', 'get_c4_reservas', 'get_c5_spread',
    'get_g1_vix', 'get_g2_dxy', 'get_g3_us10y', 'get_g4_hy_spread', 'get_g5_copper',
    'get_g6_google_trends', 'get_g7_volatility', 'get_fed_funds_rate', 'get_usdmxn',
    'get_o1_brent', 'get_o2_gas_europe', 'get_o3_usdchf', 'get_o4_sofr', 'get_o5_war_risk',
    'get_m1_usdmxn', 'get_m2_corn', 'get_m3_urea',
    'get_g8_carry_trade',
]
