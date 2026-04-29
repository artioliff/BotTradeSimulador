# estrategias/__init__.py
# Este arquivo pode estar vazio, mas e necessario para Python reconhecer a pasta como um modulo

from .base import EstrategiaBase
from .grid_spot import GridSpotStrategy
from .media_movel import MediaMovelStrategy
from .rsi import RSIStrategy
from .rsi_avancado import RSIAvancadoStrategy
from .macd import MACDStrategy
from .bollinger import BollingerBandsStrategy
from .suporte_resistencia import SuporteResistenciaStrategy
from .mean_reversion import MeanReversionStrategy
from .adx import ADXStrategy
from .multi_timeframe import MultiTimeframeStrategy
from .scalping import ScalpingStrategy
from .combinacao import CombinacaoStrategy

__all__ = [
    'EstrategiaBase',
    'GridSpotStrategy', 
    'MediaMovelStrategy',
    'RSIStrategy',
    'RSIAvancadoStrategy',
    'MACDStrategy',
    'BollingerBandsStrategy',
    'SuporteResistenciaStrategy',
    'MeanReversionStrategy',
    'ADXStrategy',
    'MultiTimeframeStrategy',
    'ScalpingStrategy',
    'CombinacaoStrategy'
]