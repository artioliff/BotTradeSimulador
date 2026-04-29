from .base import EstrategiaBase
from collections import deque

class MACDStrategy(EstrategiaBase):
    """
    Estratégia baseada no MACD.
    Compra quando linha MACD cruza acima do sinal.
    Vende quando linha MACD cruza abaixo do sinal.
    """
    
    def __init__(self, symbol, fast_period=12, slow_period=26, signal_period=9,
                 quantidade_por_trade=0.001, saldo_inicial=10000):
        super().__init__(symbol, saldo_inicial)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.quantidade_por_trade = quantidade_por_trade
        self.historico_precos = deque(maxlen=1000)
        self.historico_macd = deque(maxlen=500)
        self.em_posicao = False
    
    def calcular_macd(self, precos):
        """Calcula MACD, Signal e Histograma"""
        if len(precos) < self.slow_period + self.signal_period:
            return None, None, None
        
        # Calcula EMAs
        ema_fast = self._calcular_ema(precos, self.fast_period)
        ema_slow = self._calcular_ema(precos, self.slow_period)
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line (EMA do MACD)
        macd_signal = self._calcular_ema_de_lista(macd_line, self.signal_period)
        
        # Histograma
        histograma = macd_line - macd_signal
        
        return macd_line, macd_signal, histograma
    
    def _calcular_ema(self, precos, periodo):
        """Calcula EMA para uma lista de preços"""
        if len(precos) < periodo:
            return precos[-1] if precos else 0
        
        # EMA suavizado
        multiplicador = 2 / (periodo + 1)
        ema = precos[0]
        
        for preco in precos[1:]:
            ema = (preco - ema) * multiplicador + ema
        
        return ema
    
    def processar_preco(self, preco, timestamp):
        self.historico_precos.append(preco)
        
        if len(self.historico_precos) < self.slow_period + self.signal_period:
            return []
        
        macd, signal, hist = self.calcular_macd(self.historico_precos)
        
        if macd is None:
            return []
        
        ordens = []
        
        # Sinal de compra: MACD cruza acima do sinal
        if len(self.historico_macd) > 0:
            macd_anterior, signal_anterior = self.historico_macd[-1][:2]
            
            if macd_anterior <= signal_anterior and macd > signal and not self.em_posicao:
                trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                            macd=round(macd, 4), sinal=round(signal, 4))
                if trade:
                    self.em_posicao = True
                    ordens.append(trade)
            
            elif macd_anterior >= signal_anterior and macd < signal and self.em_posicao:
                trade = self.executar_venda(preco, self.quantidade_por_trade, timestamp,
                                           macd=round(macd, 4), sinal=round(signal, 4))
                if trade:
                    self.em_posicao = False
                    ordens.append(trade)
        
        self.historico_macd.append((macd, signal, hist))
        return ordens
    
    def reset(self):
        """Reseta a estrategia"""
        super().reset()
        self.historico_precos = deque(maxlen=1000)
        self.historico_macd = deque(maxlen=500)
        self.em_posicao = False