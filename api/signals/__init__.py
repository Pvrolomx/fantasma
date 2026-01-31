"""FANTASMA Signals Package"""
from .banxico import get_c1_fix, get_c2_tiie, get_c4_reservas
from .cftc import get_c3_cftc
from .fred import get_g1_vix, get_g3_us10y, get_c5_spread, get_fed_funds_rate
from .yahoo import get_g2_dxy, get_g4_hy_spread, get_g5_copper, get_usdmxn
from .google_trends import get_g6_google_trends
from .volatility import get_g7_volatility

__all__ = [
    'get_c1_fix',
    'get_c2_tiie', 
    'get_c3_cftc',
    'get_c4_reservas',
    'get_c5_spread',
    'get_g1_vix',
    'get_g2_dxy',
    'get_g3_us10y',
    'get_g4_hy_spread',
    'get_g5_copper',
    'get_g6_google_trends',
    'get_g7_volatility',
    'get_fed_funds_rate',
    'get_usdmxn'
]
