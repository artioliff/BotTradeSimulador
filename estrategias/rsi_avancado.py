from .base import EstrategiaBase
from collections import deque

class RSIAvancadoStrategy(EstrategiaBase):
    """
    Estrategia RSI Avancada com multiplos sinais:
    - Divergencia entre preco e RSI
    - Cruzamento de niveis
    - Filtro de tendencia
    """
    
    def __init__(self, symbol, periodo=14, limite_inferior=30, limite_superior=70,
                 quantidade_por_trade=0.001, saldo_inicial=10000,
                 usar_divergencia=True, usar_filtro_tendencia=True,
                 periodo_tendencia=200):
        """
        Args:
            usar_divergencia (bool): Se True, busca divergencias entre preco e RSI
            usar_filtro_tendencia (bool): Se True, so opera na direcao da tendencia
            periodo_tendencia (int): Periodo para media movel de tendencia
        """
        super().__init__(symbol, saldo_inicial)
        self.periodo = periodo
        self.limite_inferior = limite_inferior
        self.limite_superior = limite_superior
        self.quantidade_por_trade = quantidade_por_trade
        self.usar_divergencia = usar_divergencia
        self.usar_filtro_tendencia = usar_filtro_tendencia
        self.periodo_tendencia = periodo_tendencia
        
        # Historicos
        self.historico_precos = deque(maxlen=1000)
        self.historico_rsi = deque(maxlen=1000)
        self.historico_tendencia = deque(maxlen=200)
        
        # Controle
        self.em_posicao = False
        self.divergencia_alta = False
        self.divergencia_baixa = False
    
    def detectar_divergencia(self, lookback=20):
        """Detecta divergencias usando análise de pivôs locais"""
        if len(self.historico_precos) < lookback:
            return False, False
        
        precos = self.historico_precos[-lookback:]
        rsis = [h['rsi'] for h in self.historico_rsi[-lookback:]]
        
        preco_min_local = None
        rsi_min_local = None
        preco_max_local = None
        rsi_max_local = None
        
        for i in range(2, len(precos) - 2):
            if precos[i-1] > precos[i] < precos[i+1]:
                if preco_min_local is None or precos[i] < preco_min_local['preco']:
                    preco_min_local = {'index': i, 'preco': precos[i]}
                    rsi_min_local = {'index': i, 'rsi': rsis[i]}
            
            if precos[i-1] < precos[i] > precos[i+1]:
                if preco_max_local is None or precos[i] > preco_max_local['preco']:
                    preco_max_local = {'index': i, 'preco': precos[i]}
                    rsi_max_local = {'index': i, 'rsi': rsis[i]}
        
        divergencia_alta = False
        divergencia_baixa = False
        
        if preco_min_local and rsi_min_local:
            if preco_min_local['preco'] < precos[-5]:
                if rsi_min_local['rsi'] > rsis[-2] or rsi_min_local['rsi'] > 35:
                    divergencia_alta = True
        
        if preco_max_local and rsi_max_local:
            if preco_max_local['preco'] > precos[-5]:
                if rsi_max_local['rsi'] < rsis[-2] or rsi_max_local['rsi'] < 65:
                    divergencia_baixa = True
        
        return divergencia_alta, divergencia_baixa
    
    def calcular_tendencia(self):
        """Calcula tendencia baseada em media movel de longo prazo"""
        if len(self.historico_precos) < self.periodo_tendencia:
            return 'NEUTRO'
        
        media_longa = sum(self.historico_precos[-self.periodo_tendencia:]) / self.periodo_tendencia
        preco_atual = self.historico_precos[-1]
        
        if preco_atual > media_longa * 1.02:
            return 'ALTA'
        elif preco_atual < media_longa * 0.98:
            return 'BAIXA'
        else:
            return 'LATERAL'
    
    def processar_preco(self, preco, timestamp):
        """Processa preco com sinais avancados de RSI"""
        self.ultimo_preco = preco
        self.historico_precos.append(preco)
        
        if len(self.historico_precos) < max(self.periodo + 1, self.periodo_tendencia):
            return []
        
        # Calcula RSI
        rsi = self.calcular_rsi_wilder(self.historico_precos, self.periodo)
        self.historico_rsi.append({'timestamp': timestamp, 'rsi': rsi, 'preco': preco})
        
        # Detecta divergencias
        if self.usar_divergencia and len(self.historico_precos) > 20:
            div_alta, div_baixa = self.detectar_divergencia()
            if div_alta:
                self.divergencia_alta = True
                print(f"  [DIVERGENCIA ALTA] Detectada! Possivel reversao para cima")
            if div_baixa:
                self.divergencia_baixa = True
                print(f"  [DIVERGENCIA BAIXA] Detectada! Possivel reversao para baixo")
        
        # Calcula tendencia
        tendencia = self.calcular_tendencia() if self.usar_filtro_tendencia else 'NEUTRO'
        
        # Log periodico
        if len(self.historico_rsi) % 10 == 0:
            print(f"  RSI: {rsi:.1f} | Tendencia: {tendencia} | Divergencia Alta: {self.divergencia_alta}")
        
        ordens_executadas = []
        
        # SINAIS DE COMPRA
        comprar = False
        motivo_compra = ""
        
        # Sinal 1: RSI em sobrevenda
        if rsi <= self.limite_inferior:
            comprar = True
            motivo_compra = "SOBREVENDA"
        
        # Sinal 2: Divergencia de alta (mais forte)
        if self.usar_divergencia and self.divergencia_alta:
            comprar = True
            motivo_compra = "DIVERGENCIA_ALTA"
            self.divergencia_alta = False  # Reseta
        
        # Filtro de tendencia (so compra em tendencia de alta ou lateral)
        if self.usar_filtro_tendencia and tendencia == 'BAIXA' and motivo_compra == "SOBREVENDA":
            comprar = False  # Nao compra em tendencia de baixa
        
        if comprar and not self.em_posicao:
            trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                        rsi=rsi, motivo=motivo_compra, tendencia=tendencia)
            if trade:
                self.em_posicao = True
                ordens_executadas.append(trade)
        
        # SINAIS DE VENDA
        vender = False
        motivo_venda = ""
        
        # Sinal 1: RSI em sobrecompra
        if rsi >= self.limite_superior:
            vender = True
            motivo_venda = "SOBRECOMPRA"
        
        # Sinal 2: Divergencia de baixa
        if self.usar_divergencia and self.divergencia_baixa:
            vender = True
            motivo_venda = "DIVERGENCIA_BAIXA"
            self.divergencia_baixa = False
        
        # Filtro de tendencia (vende mais cedo em tendencia de baixa)
        if self.usar_filtro_tendencia and tendencia == 'BAIXA' and rsi >= 50:
            vender = True
            motivo_venda = "TENDENCIA_BAIXA"
        
        if vender and self.em_posicao:
            trade = self.executar_venda(preco, self.posicao, timestamp,
                                       rsi=rsi, motivo=motivo_venda, tendencia=tendencia)
            if trade:
                self.em_posicao = False
                ordens_executadas.append(trade)
        
        return ordens_executadas
    
    def reset(self):
        """Reseta a estrategia"""
        super().reset()
        self.historico_precos = deque(maxlen=1000)
        self.historico_rsi = deque(maxlen=1000)
        self.historico_tendencia = deque(maxlen=200)
        self.em_posicao = False
        self.divergencia_alta = False
        self.divergencia_baixa = False
    
    def get_configuracao(self):
        return {
            'nome': 'RSI Avancado',
            'descricao': 'RSI com deteccao de divergencias e filtro de tendencia',
            'parametros': {
                'periodo_rsi': self.periodo,
                'sobrevenda': self.limite_inferior,
                'sobrecompra': self.limite_superior,
                'quantidade_por_trade': self.quantidade_por_trade,
                'saldo_inicial_usdt': self.saldo_inicial,
                'detectar_divergencias': self.usar_divergencia,
                'filtrar_tendencia': self.usar_filtro_tendencia,
                'periodo_tendencia': self.periodo_tendencia
            }
        }