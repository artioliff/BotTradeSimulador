# estrategias/rsi_avancado.py
from .base import EstrategiaBase
from collections import deque
from datetime import datetime

class RSIAvancadoStrategy(EstrategiaBase):
    """
    Estrategia RSI Avancada com multiplos sinais (Versão Corrigida):
    - Divergencia entre preco e RSI (detecção correta)
    - Cruzamento de niveis de sobrecompra/sobrevenda
    - Filtro de tendencia com EMA multiplas
    - Proteções: Stop-Loss, Take-Profit, Trailing Stop
    - Cooldown após perdas consecutivas
    """
    
    def __init__(self, symbol, periodo=14, limite_inferior=30, limite_superior=70,
                 quantidade_por_trade=0.001, percentual_por_trade=None, saldo_inicial=10000,
                 usar_divergencia=True, usar_filtro_tendencia=True,
                 periodo_tendencia=200, usar_ema_multipla=True,
                 stop_loss_percent=0.02, take_profit_percent=0.03,
                 trailing_stop_percent=0.01, usar_saida_gradual=False,
                 max_perdas_consecutivas=3, cooldown_periods=10,
                 debug=False):
        """
        Args:
            symbol: Simbolo do ativo
            periodo: Periodo do RSI (padrao: 14)
            limite_inferior: Limite de sobrevenda (padrao: 30)
            limite_superior: Limite de sobrecompra (padrao: 70)
            quantidade_por_trade: Quantidade fixa por operacao
            percentual_por_trade: Percentual do saldo a usar
            saldo_inicial: Saldo inicial em USDT
            usar_divergencia: Se True, busca divergencias entre preco e RSI
            usar_filtro_tendencia: Se True, so opera na direcao da tendencia
            periodo_tendencia: Periodo para media movel de tendencia
            usar_ema_multipla: Se True, usa EMAs 9/21 para tendencia
            stop_loss_percent: Percentual de stop-loss
            take_profit_percent: Percentual de take-profit
            trailing_stop_percent: Percentual de trailing stop
            usar_saida_gradual: Se True, vende em partes
            max_perdas_consecutivas: Maximo de perdas seguidas antes de pausar
            cooldown_periods: Quantos candles esperar apos muitas perdas
            debug: Se True, exibe logs detalhados
        """
        super().__init__(symbol, saldo_inicial, debug=debug)
        
        # Parametros RSI
        self.periodo = periodo
        self.limite_inferior = limite_inferior
        self.limite_superior = limite_superior
        self.quantidade_por_trade = quantidade_por_trade
        self.percentual_por_trade = percentual_por_trade
        
        # Filtros
        self.usar_divergencia = usar_divergencia
        self.usar_filtro_tendencia = usar_filtro_tendencia
        self.periodo_tendencia = periodo_tendencia
        self.usar_ema_multipla = usar_ema_multipla
        
        # Proteções
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.trailing_stop_percent = trailing_stop_percent
        self.usar_saida_gradual = usar_saida_gradual
        self.max_perdas_consecutivas = max_perdas_consecutivas
        self.cooldown_periods_counter = 0
        self.cooldown_max_periods = cooldown_periods
        
        # Historicos
        self.historico_rsi = deque(maxlen=1000)
        self.historico_volumes = deque(maxlen=1000)
        
        # Estado
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
        self.perdas_consecutivas = 0
        self.volume_atual = 0
        
        # Divergencias
        self.ultimos_pivos_preco = deque(maxlen=10)
        self.ultimos_pivos_rsi = deque(maxlen=10)
        self.divergencia_alta_pendente = False
        self.divergencia_baixa_pendente = False
        self.divergencia_confirmada_alta = False
        self.divergencia_confirmada_baixa = False
        
        # Estatisticas
        self.sinais_compra = {'RSI': 0, 'DIVERGENCIA': 0, 'TENDENCIA': 0}
        self.sinais_venda = {'RSI': 0, 'DIVERGENCIA': 0, 'TENDENCIA': 0}
    
    def _encontrar_pivos(self, dados, lookback=5):
        """Encontra pontos de mínimo e máximo locais"""
        if len(dados) < lookback * 2:
            return [], []
        
        minimos = []
        maximos = []
        
        for i in range(lookback, len(dados) - lookback):
            # Verifica se é mínimo local
            is_min = True
            for j in range(1, lookback + 1):
                if dados[i] >= dados[i - j] or dados[i] >= dados[i + j]:
                    is_min = False
                    break
            
            if is_min:
                minimos.append({'index': i, 'valor': dados[i]})
            
            # Verifica se é máximo local
            is_max = True
            for j in range(1, lookback + 1):
                if dados[i] <= dados[i - j] or dados[i] <= dados[i + j]:
                    is_max = False
                    break
            
            if is_max:
                maximos.append({'index': i, 'valor': dados[i]})
        
        return minimos, maximos
    
    def _detectar_divergencia_alta(self, precos, rsis):
        """
        Detecta divergência de alta (bullish divergence):
        Preço faz mínimo mais baixo, RSI faz mínimo mais alto
        """
        if len(precos) < 30 or len(rsis) < 30:
            return False
        
        # Encontra pivôs de mínimo
        minimos_preco, _ = self._encontrar_pivos(precos, lookback=3)
        minimos_rsi, _ = self._encontrar_pivos(rsis, lookback=3)
        
        if len(minimos_preco) < 2 or len(minimos_rsi) < 2:
            return False
        
        # Pega os dois últimos mínimos
        ultimo_min_preco = minimos_preco[-1]
        penultimo_min_preco = minimos_preco[-2]
        
        ultimo_min_rsi = minimos_rsi[-1]
        penultimo_min_rsi = minimos_rsi[-2]
        
        # Divergência de alta: preço mais baixo, RSI mais alto
        preco_mais_baixo = ultimo_min_preco['valor'] < penultimo_min_preco['valor']
        rsi_mais_alto = ultimo_min_rsi['valor'] > penultimo_min_rsi['valor']
        
        # Verifica se o RSI está em zona de sobrevenda ou próximo
        rsi_em_sobrevenda = ultimo_min_rsi['valor'] <= self.limite_inferior + 10
        
        if preco_mais_baixo and rsi_mais_alto and rsi_em_sobrevenda:
            self._log(f"Divergência de ALTA detectada! Preço: {penultimo_min_preco['valor']:.2f} -> {ultimo_min_preco['valor']:.2f}, RSI: {penultimo_min_rsi['valor']:.1f} -> {ultimo_min_rsi['valor']:.1f}", "SINAL")
            return True
        
        return False
    
    def _detectar_divergencia_baixa(self, precos, rsis):
        """
        Detecta divergência de baixa (bearish divergence):
        Preço faz máximo mais alto, RSI faz máximo mais baixo
        """
        if len(precos) < 30 or len(rsis) < 30:
            return False
        
        # Encontra pivôs de máximo
        _, maximos_preco = self._encontrar_pivos(precos, lookback=3)
        _, maximos_rsi = self._encontrar_pivos(rsis, lookback=3)
        
        if len(maximos_preco) < 2 or len(maximos_rsi) < 2:
            return False
        
        # Pega os dois últimos máximos
        ultimo_max_preco = maximos_preco[-1]
        penultimo_max_preco = maximos_preco[-2]
        
        ultimo_max_rsi = maximos_rsi[-1]
        penultimo_max_rsi = maximos_rsi[-2]
        
        # Divergência de baixa: preço mais alto, RSI mais baixo
        preco_mais_alto = ultimo_max_preco['valor'] > penultimo_max_preco['valor']
        rsi_mais_baixo = ultimo_max_rsi['valor'] < penultimo_max_rsi['valor']
        
        # Verifica se o RSI está em zona de sobrecompra ou próximo
        rsi_em_sobrecompra = ultimo_max_rsi['valor'] >= self.limite_superior - 10
        
        if preco_mais_alto and rsi_mais_baixo and rsi_em_sobrecompra:
            self._log(f"Divergência de BAIXA detectada! Preço: {penultimo_max_preco['valor']:.2f} -> {ultimo_max_preco['valor']:.2f}, RSI: {penultimo_max_rsi['valor']:.1f} -> {ultimo_max_rsi['valor']:.1f}", "SINAL")
            return True
        
        return False
    
    def _calcular_ema_multipla(self):
        """Calcula EMAs 9, 21 e SMA 200 usando métodos da classe base"""
        if len(self.historico_precos) < 200:
            return None, None, None

        ema9 = self.calcular_media_movel_exponencial(self.historico_precos, 9)
        ema21 = self.calcular_media_movel_exponencial(self.historico_precos, 21)
        precos_lista = list(self.historico_precos)
        sma200 = sum(precos_lista[-200:]) / 200

        return ema9, ema21, sma200
    
    def _calcular_tendencia(self):
        """Calcula tendencia baseada em EMAs e preço"""
        if len(self.historico_precos) < self.periodo_tendencia:
            return 'NEUTRO', 0
        
        preco_atual = self.historico_precos[-1]
        
        if self.usar_ema_multipla:
            ema9, ema21, sma200 = self._calcular_ema_multipla()
            
            if ema9 is None:
                return 'NEUTRO', 0
            
            # Tendência de alta: EMA9 > EMA21 > SMA200 e preço > EMA9
            if ema9 > ema21 > sma200 and preco_atual > ema9:
                forca = (ema9 - sma200) / sma200 * 100
                return 'ALTA', forca
            
            # Tendência de baixa: EMA9 < EMA21 < SMA200 e preço < EMA9
            elif ema9 < ema21 < sma200 and preco_atual < ema9:
                forca = (sma200 - ema9) / sma200 * 100
                return 'BAIXA', forca
            
            elif preco_atual > sma200:
                return 'LATERAL_ALTA', 0
            elif preco_atual < sma200:
                return 'LATERAL_BAIXA', 0
            else:
                return 'LATERAL', 0
        else:
            # Método simples: compara com SMA
            precos_lista_tendencia = list(self.historico_precos)
            media_longa = sum(precos_lista_tendencia[-self.periodo_tendencia:]) / self.periodo_tendencia
            
            if preco_atual > media_longa * 1.05:  # 5% acima
                return 'ALTA', (preco_atual - media_longa) / media_longa * 100
            elif preco_atual < media_longa * 0.95:  # 5% abaixo
                return 'BAIXA', (media_longa - preco_atual) / media_longa * 100
            else:
                return 'LATERAL', 0
    
    def _calcular_quantidade(self, preco: float):
        if self.percentual_por_trade:
            valor_investir = self.saldo_usdt * self.percentual_por_trade
            quantidade = round(valor_investir / preco, 8)
            return quantidade, valor_investir
        else:
            quantidade = self.quantidade_por_trade
            valor_necessario = quantidade * preco
            
            if valor_necessario > self.saldo_usdt:
                self._log(f"Saldo insuficiente! Necessário ${valor_necessario:.2f}, tem ${self.saldo_usdt:.2f}", "ERRO")
                return None, None
            
            return quantidade, valor_necessario
    
    def processar_preco(self, preco, timestamp, volume=None, **kwargs):
        """
        Processa cada preco com sinais avançados de RSI
        
        Args:
            preco: Preco atual
            timestamp: Timestamp do candle
            volume: Volume do candle (opcional)
        """
        self.ultimo_preco = preco
        self.historico_precos.append(preco)
        
        if volume is not None:
            self.volume_atual = volume
            self.historico_volumes.append(volume)
        
        # ============================================
        # COOLDOWN
        # ============================================
        if self.cooldown_periods_counter > 0:
            self.cooldown_periods_counter -= 1
            if self.cooldown_periods_counter == 0:
                self._log("COOLDOWN encerrado - Retomando operações", "INFO")
            return []
        
        # ============================================
        # DADOS SUFICIENTES?
        # ============================================
        if len(self.historico_precos) < max(self.periodo + 1, self.periodo_tendencia):
            return []
        
        # ============================================
        # CALCULA RSI
        # ============================================
        rsi = self.calcular_rsi_wilder(self.historico_precos, self.periodo)
        self.historico_rsi.append({'timestamp': timestamp, 'rsi': rsi, 'preco': preco})
        
        # ============================================
        # DETECTA DIVERGENCIAS
        # ============================================
        if self.usar_divergencia and len(self.historico_precos) > 50:
            precos_lista = list(self.historico_precos)
            rsis_lista = [r['rsi'] for r in self.historico_rsi]
            
            div_alta = self._detectar_divergencia_alta(precos_lista, rsis_lista)
            div_baixa = self._detectar_divergencia_baixa(precos_lista, rsis_lista)
            
            self.divergencia_confirmada_alta = div_alta
            self.divergencia_confirmada_baixa = div_baixa
        
        # ============================================
        # CALCULA TENDENCIA
        # ============================================
        tendencia, forca_tendencia = self._calcular_tendencia() if self.usar_filtro_tendencia else ('NEUTRO', 0)
        
        # ============================================
        # LOG PERIODICO
        # ============================================
        if len(self.historico_rsi) % 10 == 0:
            div_status = ""
            if self.divergencia_confirmada_alta:
                div_status = " | DIV_ALTA"
            elif self.divergencia_confirmada_baixa:
                div_status = " | DIV_BAIXA"
            
            print(f"  RSI: {rsi:.1f} | Tendência: {tendencia}{div_status}")
        
        ordens_executadas = []
        
        # ============================================
        # VERIFICA PROTECÇÕES (Stop, Take, Trailing)
        # ============================================
        if self.em_posicao:
            trade_protecao = self._verificar_stop_take_trailing(
                preco, timestamp, self.stop_loss_percent, self.take_profit_percent,
                self.trailing_stop_percent, rsi=rsi)
            if trade_protecao:
                if trade_protecao['motivo'] == 'STOP_LOSS':
                    self.perdas_consecutivas += 1
                    self._log(f"Perdas consecutivas: {self.perdas_consecutivas}/{self.max_perdas_consecutivas}")
                    if self.perdas_consecutivas >= self.max_perdas_consecutivas:
                        self.cooldown_periods_counter = self.cooldown_max_periods
                        self._log(f"COOLDOWN ativado por {self.cooldown_max_periods} candles")
                        self.perdas_consecutivas = 0
                else:
                    self.perdas_consecutivas = 0
                ordens_executadas.append(trade_protecao)
                return ordens_executadas
        
        # ============================================
        # SINAIS DE COMPRA
        # ============================================
        comprar = False
        motivo_compra = ""
        peso_sinal = 0
        
        # Sinal 1: RSI em sobrevenda (peso 1)
        if rsi <= self.limite_inferior:
            comprar = True
            motivo_compra = "RSI_SOBREVENDA"
            peso_sinal = 1
            self.sinais_compra['RSI'] += 1
        
        # Sinal 2: Divergência de alta (peso 2 - mais forte)
        if self.usar_divergencia and self.divergencia_confirmada_alta:
            comprar = True
            motivo_compra = "DIVERGENCIA_ALTA"
            peso_sinal = 2
            self.sinais_compra['DIVERGENCIA'] += 1
            self.divergencia_confirmada_alta = False  # Reseta após uso
        
        # Sinal 3: Tendência de alta (peso 0.5 - confirmação)
        if self.usar_filtro_tendencia and tendencia in ['ALTA', 'LATERAL_ALTA']:
            peso_sinal += 0.5
        
        # Filtro: não comprar em tendência de baixa forte
        if self.usar_filtro_tendencia and tendencia == 'BAIXA' and forca_tendencia > 5:
            if motivo_compra != "DIVERGENCIA_ALTA":  # Divergência pode superar
                comprar = False
                self._log(f"Tendência de baixa forte ({forca_tendencia:.1f}%), ignorando compra", "FILTRO")
        
        # Executa compra
        if comprar and not self.em_posicao:
            quantidade, valor = self._calcular_quantidade(preco)
            
            if quantidade and quantidade > 0:
                trade = self.executar_compra(preco, quantidade, timestamp,
                                            rsi=round(rsi, 1),
                                            motivo=motivo_compra,
                                            tendencia=tendencia,
                                            peso_sinal=peso_sinal)
                
                if trade:
                    self.em_posicao = True
                    self.preco_compra_medio = preco
                    self.quantidade_comprada_total = quantidade
                    self.maior_preco_posicao = preco
                    ordens_executadas.append(trade)
                    
                    self._log(f"SINAL DE COMPRA: {motivo_compra} (peso {peso_sinal})", "SINAL")
        
        # ============================================
        # SINAIS DE VENDA
        # ============================================
        vender = False
        motivo_venda = ""
        peso_sinal_venda = 0
        
        # Sinal 1: RSI em sobrecompra
        if rsi >= self.limite_superior:
            vender = True
            motivo_venda = "RSI_SOBRECOMPRA"
            peso_sinal_venda = 1
            self.sinais_venda['RSI'] += 1
        
        # Sinal 2: Divergência de baixa (mais forte)
        if self.usar_divergencia and self.divergencia_confirmada_baixa:
            vender = True
            motivo_venda = "DIVERGENCIA_BAIXA"
            peso_sinal_venda = 2
            self.sinais_venda['DIVERGENCIA'] += 1
            self.divergencia_confirmada_baixa = False
        
        # Sinal 3: Venda antecipada em tendência de baixa
        if self.usar_filtro_tendencia and tendencia == 'BAIXA' and rsi >= 50:
            vender = True
            motivo_venda = "TENDENCIA_BAIXA"
            peso_sinal_venda = 1.5
            self.sinais_venda['TENDENCIA'] += 1
        
        # Executa venda
        if vender and self.em_posicao:
            quantidade_vender = self.quantidade_comprada_total
            
            # Saída gradual
            if self.usar_saida_gradual and self.preco_compra_medio > 0:
                ganho = (preco - self.preco_compra_medio) / self.preco_compra_medio
                
                if ganho >= 0.06:
                    quantidade_vender = self.quantidade_comprada_total
                elif ganho >= 0.04:
                    quantidade_vender = self.quantidade_comprada_total * 0.5
                elif ganho >= 0.02:
                    quantidade_vender = self.quantidade_comprada_total * 0.25
                else:
                    quantidade_vender = self.quantidade_comprada_total
            
            if quantidade_vender > 0:
                trade = self.executar_venda(preco, quantidade_vender, timestamp,
                                           rsi=round(rsi, 1),
                                           motivo=motivo_venda,
                                           tendencia=tendencia,
                                           peso_sinal=peso_sinal_venda)
                
                if trade:
                    self.quantidade_comprada_total -= quantidade_vender
                    
                    if self.quantidade_comprada_total <= 0.00000001:
                        self.em_posicao = False
                        self.quantidade_comprada_total = 0
                        self.preco_compra_medio = 0
                        self.maior_preco_posicao = 0
                    
                    ordens_executadas.append(trade)
                    self._log(f"SINAL DE VENDA: {motivo_venda} (peso {peso_sinal_venda})", "SINAL")
        
        return ordens_executadas
    
    def reset(self):
        """Reseta a estrategia"""
        super().reset()
        self.historico_rsi = deque(maxlen=1000)
        self.historico_volumes = deque(maxlen=1000)
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
        self.perdas_consecutivas = 0
        self.cooldown_periods_counter = 0
        self.ultimos_pivos_preco = deque(maxlen=10)
        self.ultimos_pivos_rsi = deque(maxlen=10)
        self.divergencia_alta_pendente = False
        self.divergencia_baixa_pendente = False
        self.divergencia_confirmada_alta = False
        self.divergencia_confirmada_baixa = False
        self.sinais_compra = {'RSI': 0, 'DIVERGENCIA': 0, 'TENDENCIA': 0}
        self.sinais_venda = {'RSI': 0, 'DIVERGENCIA': 0, 'TENDENCIA': 0}
    
    def get_configuracao(self):
        """Retorna a configuracao atual da estrategia"""
        if self.percentual_por_trade:
            gestao_quantidade = f"{self.percentual_por_trade*100}% do saldo"
        else:
            simbolo_asset = self.symbol.replace('USDT', '')
            gestao_quantidade = f"{self.quantidade_por_trade} {simbolo_asset} (fixo)"
        
        return {
            'nome': 'RSI Avançado (Versão Corrigida)',
            'descricao': 'RSI com detecção CORRETA de divergências, filtro de tendência com EMAs múltiplas, stop-loss, take-profit, trailing stop e cooldown após perdas consecutivas.',
            'parametros': {
                'periodo_rsi': self.periodo,
                'sobrevenda': self.limite_inferior,
                'sobrecompra': self.limite_superior,
                'gestao_de_quantidade': gestao_quantidade,
                'saldo_inicial_usdt': self.saldo_inicial,
                'detectar_divergencias': self.usar_divergencia,
                'filtrar_tendencia': self.usar_filtro_tendencia,
                'usar_ema_multipla': self.usar_ema_multipla,
                'periodo_tendencia': self.periodo_tendencia,
                'stop_loss_percentual': f"{self.stop_loss_percent * 100}%",
                'take_profit_percentual': f"{self.take_profit_percent * 100}%",
                'trailing_stop_percentual': f"{self.trailing_stop_percent * 100}%",
                'saida_gradual': self.usar_saida_gradual,
                'max_perdas_consecutivas': self.max_perdas_consecutivas,
                'cooldown_apos_perdas': self.cooldown_max_periods
            }
        }
    
    def get_estatisticas_sinais(self):
        """Retorna estatísticas dos sinais gerados"""
        return {
            'sinais_compra': self.sinais_compra,
            'sinais_venda': self.sinais_venda,
            'total_sinais_compra': sum(self.sinais_compra.values()),
            'total_sinais_venda': sum(self.sinais_venda.values())
        }