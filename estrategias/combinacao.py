# estrategias/combinacao.py
from .base import EstrategiaBase
from collections import deque

class CombinacaoStrategy(EstrategiaBase):
    """
    Estrategia que combina RSI, MACD e Bollinger Bands.
    Só opera quando pelo menos 2 indicadores concordam.
    """
    
    def __init__(self, symbol, periodo_rsi=14, limite_rsi_inf=30, limite_rsi_sup=70,
                 macd_fast=12, macd_slow=26, macd_signal=9,
                 bb_periodo=20, bb_desvios=2,
                 quantidade_por_trade=0.001, saldo_inicial=10000):
        super().__init__(symbol, saldo_inicial)
        
        # RSI params
        self.periodo_rsi = periodo_rsi
        self.limite_rsi_inf = limite_rsi_inf
        self.limite_rsi_sup = limite_rsi_sup
        
        # MACD params
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        
        # Bollinger params
        self.bb_periodo = bb_periodo
        self.bb_desvios = bb_desvios
        
        self.quantidade_por_trade = quantidade_por_trade
        self.historico_precos = deque(maxlen=2000)
        self.historico_macd = deque(maxlen=500)
        self.em_posicao = False
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
    
    def calcular_rsi(self, precos):
        """Calcula RSI usando método da classe base"""
        return self.calcular_rsi_wilder(precos, self.periodo_rsi)
    
    def calcular_macd(self, precos):
        """Calcula MACD line e Signal"""
        if len(precos) < self.macd_slow + self.macd_signal:
            return 0, 0
        
        # Calcula EMAs
        ema_fast = self._calcular_ema(precos, self.macd_fast)
        ema_slow = self._calcular_ema(precos, self.macd_slow)
        
        macd_line = ema_fast - ema_slow
        
        # Calcula signal EMA do MACD
        if len(self.historico_macd) >= self.macd_signal:
            macd_values = [m[0] for m in self.historico_macd[-self.macd_signal:]]
            macd_values.append(macd_line)
            macd_signal_line = self._calcular_ema_de_lista(macd_values, self.macd_signal)
        else:
            macd_signal_line = macd_line
        
        return macd_line, macd_signal_line
    
    def _calcular_ema(self, precos, periodo):
        """Calcula EMA para uma lista de preços"""
        if len(precos) < periodo:
            return precos[-1] if precos else 0
        
        multiplicador = 2 / (periodo + 1)
        ema = precos[0]
        for preco in precos[1:]:
            ema = (preco - ema) * multiplicador + ema
        return ema
    
    def _calcular_ema_de_lista(self, valores, periodo):
        """Calcula EMA para uma lista de valores"""
        if len(valores) < periodo:
            return valores[-1] if valores else 0
        
        multiplicador = 2 / (periodo + 1)
        ema = valores[0]
        for valor in valores[1:]:
            ema = (valor - ema) * multiplicador + ema
        return ema
    
    def calcular_bandas(self, precos):
        """Calcula bandas de Bollinger"""
        if len(precos) < self.bb_periodo:
            return None, None, None
        
        media = sum(precos[-self.bb_periodo:]) / self.bb_periodo
        variancia = sum((p - media) ** 2 for p in precos[-self.bb_periodo:]) / self.bb_periodo
        desvio = variancia ** 0.5
        
        banda_superior = media + (desvio * self.bb_desvios)
        banda_inferior = media - (desvio * self.bb_desvios)
        
        return banda_superior, media, banda_inferior
    
    def processar_preco(self, preco, timestamp):
        """Processa preço e combina sinais dos indicadores"""
        self.ultimo_preco = preco
        self.historico_precos.append(preco)
        
        min_precos = max(self.periodo_rsi, self.macd_slow + self.macd_signal, self.bb_periodo) + 10
        if len(self.historico_precos) < min_precos:
            return []
        
        # Calcula indicadores
        rsi = self.calcular_rsi(self.historico_precos)
        macd_line, macd_signal_line = self.calcular_macd(self.historico_precos)
        banda_sup, media_bb, banda_inf = self.calcular_bandas(self.historico_precos)
        
        # Registra MACD para histórico
        self.historico_macd.append((macd_line, macd_signal_line))
        
        # Sinais individuais
        sinal_rsi_compra = rsi <= self.limite_rsi_inf
        sinal_rsi_venda = rsi >= self.limite_rsi_sup
        
        sinal_macd_compra = macd_line > macd_signal_line
        sinal_macd_venda = macd_line < macd_signal_line
        
        sinal_bb_compra = preco <= banda_inf if banda_inf else False
        sinal_bb_venda = preco >= banda_sup if banda_sup else False
        
        # Votação
        sinais_compra = sum([sinal_rsi_compra, sinal_macd_compra, sinal_bb_compra])
        sinais_venda = sum([sinal_rsi_venda, sinal_macd_venda, sinal_bb_venda])
        
        ordens = []
        
        # Log periódico
        if len(self.historico_precos) % 20 == 0:
            print(f"  RSI: {rsi:.1f} | MACD: {macd_line:.2f} | Sinais Compra: {sinais_compra}")
        
        # ============================================
        # STOP-LOSS (2%)
        # ============================================
        if self.em_posicao and self.preco_compra_medio > 0:
            perda_percentual = (preco - self.preco_compra_medio) / self.preco_compra_medio
            if perda_percentual <= -0.02:
                print(f"  >>> STOP-LOSS ACIONADO! Perda de {perda_percentual*100:.1f}%")
                trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp, motivo='STOP_LOSS')
                if trade:
                    self.em_posicao = False
                    self.quantidade_comprada_total = 0
                    self.preco_compra_medio = 0
                    ordens.append(trade)
                    return ordens
        
        # ============================================
        # SINAIS DE COMPRA (pelo menos 2 indicadores)
        # ============================================
        if sinais_compra >= 2 and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        rsi=round(rsi, 1), 
                                        macd=round(macd_line, 4),
                                        concordancia=sinais_compra,
                                        indicadores={'rsi': sinal_rsi_compra, 
                                                    'macd': sinal_macd_compra,
                                                    'bb': sinal_bb_compra})
            if trade:
                self.em_posicao = True
                self.preco_compra_medio = preco
                self.quantidade_comprada_total = self.quantidade_por_trade
                ordens.append(trade)
        
        # ============================================
        # SINAIS DE VENDA (pelo menos 2 indicadores)
        # ============================================
        elif sinais_venda >= 2 and self.em_posicao:
            trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp,
                                       rsi=round(rsi, 1),
                                       macd=round(macd_line, 4),
                                       concordancia=sinais_venda,
                                       indicadores={'rsi': sinal_rsi_venda,
                                                   'macd': sinal_macd_venda,
                                                   'bb': sinal_bb_venda})
            if trade:
                self.em_posicao = False
                self.quantidade_comprada_total = 0
                self.preco_compra_medio = 0
                ordens.append(trade)
        
        return ordens
    
    def reset(self):
        """Reseta a estrategia"""
        super().reset()
        self.historico_precos = deque(maxlen=2000)
        self.historico_macd = deque(maxlen=500)
        self.em_posicao = False
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
    
    def get_configuracao(self):
        """Retorna a configuracao atual da estrategia"""
        return {
            'nome': 'Combinação de Indicadores (RSI + MACD + Bollinger)',
            'descricao': 'Opera quando pelo menos 2 indicadores concordam (sobrevenda/sobrecompra)',
            'parametros': {
                'periodo_rsi': self.periodo_rsi,
                'sobrevenda_rsi': self.limite_rsi_inf,
                'sobrecompra_rsi': self.limite_rsi_sup,
                'macd_rapido': self.macd_fast,
                'macd_lento': self.macd_slow,
                'macd_sinal': self.macd_signal,
                'bb_periodo': self.bb_periodo,
                'bb_desvios': self.bb_desvios,
                'quantidade_por_trade': self.quantidade_por_trade,
                'saldo_inicial_usdt': self.saldo_inicial
            }
        }